# RecruitIQ - Fix Candidates Page Issues
# This script helps diagnose and resolve issues with the candidates page

Write-Host "🔧 RecruitIQ - Candidates Page Fix Script" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

# Function to check if a service is running
function Test-ServiceRunning {
    param([string]$Url, [string]$ServiceName)
    
    try {
        Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 10 | Out-Null
        Write-Host "✅ $ServiceName is running" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ $ServiceName is not running: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Function to run Poetry commands
function Invoke-PoetryCommand {
    param([string]$Command, [string]$Description)
    
    Write-Host "📦 $Description..." -ForegroundColor Yellow
    try {
        Invoke-Expression "poetry $Command" | Out-Null
        Write-Host "✅ $Description completed successfully" -ForegroundColor Green
        return $true
    }
    catch {
        Write-Host "❌ $Description failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# Step 1: Check current directory
Write-Host "`n1. Checking current directory..." -ForegroundColor Cyan
$currentDir = Get-Location
Write-Host "Current directory: $currentDir"

if ($currentDir -notlike "*RecruitIQ*") {
    Write-Host "⚠️  Warning: You don't appear to be in the RecruitIQ directory" -ForegroundColor Yellow
    Write-Host "Please navigate to your RecruitIQ project directory first" -ForegroundColor Yellow
    exit 1
}

# Step 2: Check Poetry installation
Write-Host "`n2. Checking Poetry installation..." -ForegroundColor Cyan
try {
    $poetryVersion = poetry --version
    Write-Host "✅ Poetry is installed: $poetryVersion" -ForegroundColor Green
}
catch {
    Write-Host "❌ Poetry is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Poetry first: https://python-poetry.org/docs/#installation" -ForegroundColor Yellow
    exit 1
}

# Step 3: Install/Update dependencies
Write-Host "`n3. Installing/Updating dependencies..." -ForegroundColor Cyan
Invoke-PoetryCommand "install" "Installing dependencies"

# Step 4: Check backend health
Write-Host "`n4. Checking backend health..." -ForegroundColor Cyan
$backendRunning = Test-ServiceRunning "http://localhost:8000/health" "Backend"

# Step 5: Start backend if not running
if (-not $backendRunning) {
    Write-Host "`n5. Starting backend server..." -ForegroundColor Cyan
    Write-Host "Starting backend in background..." -ForegroundColor Yellow
    
    # Start backend in a new PowerShell window
    $backendScript = {
        Set-Location $using:currentDir
        poetry run python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    }
    
    Start-Process powershell -ArgumentList "-Command", "& {$backendScript}" -WindowStyle Normal
    
    # Wait for backend to start
    Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
    $attempts = 0
    $maxAttempts = 30
    
    do {
        Start-Sleep -Seconds 2
        $attempts++
        Write-Host "Attempt $attempts/$maxAttempts..." -ForegroundColor Gray
        $backendRunning = Test-ServiceRunning "http://localhost:8000/health" "Backend"
    } while (-not $backendRunning -and $attempts -lt $maxAttempts)
    
    if (-not $backendRunning) {
        Write-Host "❌ Backend failed to start after $maxAttempts attempts" -ForegroundColor Red
        Write-Host "Please check the backend logs for errors" -ForegroundColor Yellow
        exit 1
    }
}

# Step 6: Test candidates endpoint
Write-Host "`n6. Testing candidates endpoint..." -ForegroundColor Cyan
try {
    $candidatesResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/candidates/" -Method Get -TimeoutSec 10
    Write-Host "✅ Candidates endpoint is working" -ForegroundColor Green
    
    if ($candidatesResponse -is [System.Collections.Hashtable] -and $candidatesResponse.ContainsKey("results")) {
        $candidateCount = $candidatesResponse.results.Count
        Write-Host "📊 Found $candidateCount candidates in database" -ForegroundColor Blue
    }
    elseif ($candidatesResponse -is [System.Array]) {
        $candidateCount = $candidatesResponse.Count
        Write-Host "📊 Found $candidateCount candidates in database" -ForegroundColor Blue
    }
    else {
        Write-Host "⚠️  Unexpected response format from candidates endpoint" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "❌ Candidates endpoint test failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "This might be the cause of your candidates page issues" -ForegroundColor Yellow
}

# Step 7: Run the comprehensive test script
Write-Host "`n7. Running comprehensive diagnostics..." -ForegroundColor Cyan
if (Test-Path "test_candidates_connection.py") {
    try {
        poetry run python test_candidates_connection.py
    }
    catch {
        Write-Host "❌ Diagnostic script failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}
else {
    Write-Host "⚠️  Diagnostic script not found - skipping detailed tests" -ForegroundColor Yellow
}

# Step 8: Start frontend
Write-Host "`n8. Starting frontend..." -ForegroundColor Cyan
Write-Host "Starting Streamlit frontend..." -ForegroundColor Yellow

# Start frontend in a new PowerShell window
$frontendScript = {
    Set-Location $using:currentDir
    poetry run streamlit run frontend/app.py --server.port 8501 --server.headless false
}

Start-Process powershell -ArgumentList "-Command", "& {$frontendScript}" -WindowStyle Normal

# Wait a moment for frontend to start
Start-Sleep -Seconds 5

# Step 9: Final summary
Write-Host "`n" + "="*50 -ForegroundColor Green
Write-Host "🎯 SETUP COMPLETE" -ForegroundColor Green
Write-Host "="*50 -ForegroundColor Green

Write-Host "`n📍 Service URLs:" -ForegroundColor Cyan
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   Frontend: http://localhost:8501" -ForegroundColor White
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor White

Write-Host "`n🔍 Next Steps:" -ForegroundColor Cyan
Write-Host "1. Open your browser to http://localhost:8501" -ForegroundColor White
Write-Host "2. Navigate to the Candidates page" -ForegroundColor White
Write-Host "3. Check if the candidates are loading properly" -ForegroundColor White

Write-Host "`n🔧 If you still have issues:" -ForegroundColor Cyan
Write-Host "1. Check the PowerShell windows for error messages" -ForegroundColor White
Write-Host "2. Look at the logs in frontend.log and recruitiq.log" -ForegroundColor White
Write-Host "3. Verify your PostgreSQL database is running" -ForegroundColor White
Write-Host "4. Check the API URL setting in the Streamlit sidebar" -ForegroundColor White

Write-Host "`nPress any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 
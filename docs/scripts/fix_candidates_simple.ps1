# Simple RecruitIQ - Fix Candidates Page Issues

Write-Host "🔧 RecruitIQ - Candidates Page Fix Script" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

# Step 1: Check current directory
Write-Host "`n1. Checking current directory..." -ForegroundColor Cyan
$currentDir = Get-Location
Write-Host "Current directory: $currentDir"

# Step 2: Install dependencies
Write-Host "`n2. Installing dependencies..." -ForegroundColor Cyan
Write-Host "Running: poetry install" -ForegroundColor Yellow
poetry install

# Step 3: Check if backend is running
Write-Host "`n3. Checking backend health..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 5
    Write-Host "✅ Backend is running" -ForegroundColor Green
    $backendRunning = $true
}
catch {
    Write-Host "❌ Backend is not running" -ForegroundColor Red
    $backendRunning = $false
}

# Step 4: Start backend if not running
if (-not $backendRunning) {
    Write-Host "`n4. Starting backend server..." -ForegroundColor Cyan
    Write-Host "Starting backend in a new window..." -ForegroundColor Yellow
    
    Start-Process powershell -ArgumentList "-Command", "cd '$currentDir'; poetry run python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" -WindowStyle Normal
    
    Write-Host "Waiting for backend to start..." -ForegroundColor Yellow
    $attempts = 0
    do {
        Start-Sleep -Seconds 3
        $attempts++
        Write-Host "Attempt $attempts/10..." -ForegroundColor Gray
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get -TimeoutSec 5
            $backendRunning = $true
            Write-Host "✅ Backend started successfully" -ForegroundColor Green
        }
        catch {
            $backendRunning = $false
        }
    } while (-not $backendRunning -and $attempts -lt 10)
    
    if (-not $backendRunning) {
        Write-Host "❌ Backend failed to start" -ForegroundColor Red
        Write-Host "Please check for errors and try manually starting with:" -ForegroundColor Yellow
        Write-Host "poetry run python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor White
    }
}

# Step 5: Test candidates endpoint
Write-Host "`n5. Testing candidates endpoint..." -ForegroundColor Cyan
try {
    $candidatesResponse = Invoke-RestMethod -Uri "http://localhost:8000/api/candidates/" -Method Get -TimeoutSec 10
    Write-Host "✅ Candidates endpoint is working" -ForegroundColor Green
    
    if ($candidatesResponse.results) {
        $candidateCount = $candidatesResponse.results.Count
        Write-Host "📊 Found $candidateCount candidates in database" -ForegroundColor Blue
    }
    elseif ($candidatesResponse -is [System.Array]) {
        $candidateCount = $candidatesResponse.Count
        Write-Host "📊 Found $candidateCount candidates in database" -ForegroundColor Blue
    }
    else {
        Write-Host "📊 Candidates endpoint returned data" -ForegroundColor Blue
    }
}
catch {
    Write-Host "❌ Candidates endpoint test failed: $($_.Exception.Message)" -ForegroundColor Red
}

# Step 6: Run diagnostic test
Write-Host "`n6. Running diagnostic test..." -ForegroundColor Cyan
if (Test-Path "test_candidates_connection.py") {
    poetry run python test_candidates_connection.py
}

# Step 7: Start frontend
Write-Host "`n7. Starting frontend..." -ForegroundColor Cyan
Write-Host "Starting Streamlit frontend in a new window..." -ForegroundColor Yellow

Start-Process powershell -ArgumentList "-Command", "cd '$currentDir'; poetry run streamlit run frontend/app.py --server.port 8501" -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Host "✅ Frontend started" -ForegroundColor Green

# Final summary
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
Write-Host "2. Verify PostgreSQL database is running" -ForegroundColor White
Write-Host "3. Check API URL in Streamlit sidebar (should be http://localhost:8000/api)" -ForegroundColor White

Write-Host "`nScript completed! Check the new PowerShell windows for backend and frontend." -ForegroundColor Green 
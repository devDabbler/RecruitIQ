# RecruitIQ Quick Start Guide

This guide will help you quickly start the RecruitIQ application.

## 🚀 Easy Startup

### Option 1: Use the Startup Scripts (Recommended)

**Start Backend:**
```bash
# From the RecruitIQ root directory
python start_backend.py
```

**Start Frontend:**
```bash
# From the RecruitIQ root directory (in a new terminal)
python start_frontend.py
```

### Option 2: Manual Startup

**Start Backend:**
```bash
# Navigate to backend directory
cd backend

# Install uvicorn if not already installed
pip install uvicorn[standard]

# Start the server
python -m uvicorn main:app --reload --host localhost --port 8000
```

**Start Frontend:**
```bash
# Navigate to frontend directory
cd frontend

# Install streamlit if not already installed
pip install streamlit

# Start the application
streamlit run app.py --server.port=8501 --server.address=localhost
```

## 🌐 Application URLs

Once both services are running:

- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 💻 Windows Users

The startup scripts now use `localhost` instead of `0.0.0.0` for better Windows compatibility. If you're still having issues accessing the application:

1. Make sure Windows Firewall isn't blocking the ports
2. Try accessing via `127.0.0.1:8501` instead of `localhost:8501`
3. Check if any antivirus software is blocking the connections

## 🔧 Navigation Issue Fixes

The following issues have been fixed in this update:

### ✅ Job Detail Navigation
- Fixed job card "View Details" buttons to properly navigate to job detail pages
- Replaced HTML links with proper Streamlit navigation
- Added proper view parameter handling in main app routing

### ✅ Backend Server Issues  
- Created startup scripts that automatically install missing dependencies (uvicorn)
- Fixed import errors when starting the backend server
- Added proper error handling and user-friendly messages

### ✅ API URL Configuration
- Fixed API URL configuration inconsistencies between frontend modules
- Ensured proper `/api` path handling across all components
- Added session state initialization for API URL

### ✅ Candidate Detail Errors
- Fixed 404 errors when navigating to candidate detail pages
- Improved error handling and user feedback
- Added proper fallback navigation options

## 🐛 Troubleshooting

### Backend won't start
- Make sure you're in the RecruitIQ root directory
- Try installing uvicorn manually: `pip install uvicorn[standard]`
- Check if port 8000 is already in use

### Frontend won't start
- Make sure you're in the RecruitIQ root directory  
- Try installing streamlit manually: `pip install streamlit`
- Check if port 8501 is already in use

### Navigation issues
- Clear your browser cache and refresh the page
- Make sure both backend and frontend are running
- Check the browser console for any JavaScript errors

### 404 Errors
- Ensure the backend server is running on port 8000
- Check that the candidate/job ID exists in the database
- Verify the API URL configuration in session state

## 📝 Test Login Credentials

- **Username**: testuser
- **Password**: password

## 🎯 Next Steps

1. Start both backend and frontend using the startup scripts
2. Open http://localhost:8501 in your browser
3. Login with the test credentials
4. Navigate to the Jobs page and test the "View Details" functionality
5. Verify that job detail pages load correctly and navigation works as expected

If you continue to experience issues, please check the terminal output for error messages and ensure all dependencies are properly installed. 
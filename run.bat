@echo off
setlocal
cd /d "%~dp0"

echo ================================================================
echo DisasterVision - CLEAN START
echo ================================================================
echo.

echo [1/3] Stopping old DisasterVision processes on ports 8000 and 5517...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5517" ^| findstr "LISTENING"') do taskkill /F /PID %%P >nul 2>&1

echo [2/3] Checking Python packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Could not install the required package.
  pause
  exit /b 1
)

echo.
echo [3/3] Starting the NEW DisasterVision website...
echo.
echo Open this exact address:
echo http://127.0.0.1:8000
 echo.
python client.py
pause

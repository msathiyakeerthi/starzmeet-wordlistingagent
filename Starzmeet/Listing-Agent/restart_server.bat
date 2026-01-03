@echo off
echo Stopping Python processes...
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo Starting Flask server...
start /B python app-latest-4.py

echo Waiting for server to start...
timeout /t 5 /nobreak >nul

echo Testing server...
curl http://localhost:5000/manage -I

echo.
echo Server restarted! Open: http://localhost:5000/manage
pause








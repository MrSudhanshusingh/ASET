@echo off
title ASET - Ansh Secure Examination Technology
color 0B
cls
echo ======================================================================
echo             ASET - Ansh Secure Examination Technology
echo                  Secure. Offline. Intelligent.
echo ======================================================================
echo.

:: Check python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python.
    pause
    exit /b
)

:: Find Local LAN IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set "LAN_IP=%%a"
    goto :ip_found
)
:ip_found
set "LAN_IP=%LAN_IP: =%"

echo [INFO] Initializing SQLite database and sample records...
python seed_data.py

echo.
echo ======================================================================
echo  Server is starting! Access the portal on this machine or over LAN:
echo.
echo   Localhost Access:   http://localhost:5000
echo   Campus/Lab LAN URL: http://%LAN_IP%:5000
echo.
echo  Default Logins:
echo   - Faculty / Admin:  User: teacher   ^| Password: admin123
echo   - Student Login:    Roll: CS202601  ^| Password: student123
echo   - Exam Passcode:    SECURE2026
echo ======================================================================
echo.

python app.py
pause

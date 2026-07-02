@echo off
cd /d "%~dp0"
echo Creating virtual environment...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found in PATH. Searching common locations...
    set "PYTHON_EXE="
    for %%p in (
        "C:\Python314\python.exe"
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe"
        "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python313\python.exe"
        "C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312\python.exe"
    ) do (
        if exist %%p (
            set "PYTHON_EXE=%%~p"
            goto :found
        )
    )
    echo Python not found. Please install Python 3.12+ from https://python.org
    pause
    exit /b 1
    :found
) else (
    set "PYTHON_EXE=python"
)

echo Using: %PYTHON_EXE%
"%PYTHON_EXE%" -m venv venv
if %errorlevel% neq 0 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

echo Installing dependencies...
call venv\Scripts\activate.bat
pip install flask flask-sqlalchemy flask-login flask-wtf flask-socketio flask-migrate wtforms sqlalchemy python-dotenv geopy pillow werkzeug eventlet python-dateutil
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Setup complete! Run run.bat to start the application.
pause

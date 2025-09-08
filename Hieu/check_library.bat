@echo off
echo Checking and installing Python dependencies...

REM Check if Python is installed
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python is not found in your PATH. Please install Python and add it to your PATH.
    echo You can download Python from https://www.python.org/downloads/
    goto :eof
)

REM Check if pip is installed
where pip >nul 2>nul
if %errorlevel% neq 0 (
    echo pip is not found. Attempting to install pip...
    python -m ensurepip --default-pip
    if %errorlevel% neq 0 (
        echo Failed to install pip. Please install pip manually.
        goto :eof
    )
)

REM Ensure we are in the directory where the batch file is located (project root)
pushd "%~dp0"

REM Install dependencies from requirements.txt
if not exist "requirements.txt" (
    echo requirements.txt not found in the project root. Please ensure it exists.
    popd
    goto :eof
)

echo Installing/updating libraries from requirements.txt...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo An error occurred during installation. Please check the output above.
) else (
    echo All required libraries are installed.
)

popd
echo Done.
pause
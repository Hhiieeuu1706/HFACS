@echo off
echo ========================================
echo    AEGIS Personal Cognitive Advisor
echo    Git Push to GitHub
echo ========================================
echo.

REM Check if we're in a git repository
git status >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Not in a git repository!
    echo Please run this script from the project root directory.
    pause
    exit /b 1
)

echo [INFO] Checking git status...
git status

echo.
echo [INFO] Adding all files to staging...
git add .

echo.
echo [INFO] Checking what will be committed...
git status --porcelain

echo.
set /p commit_message="Enter commit message (or press Enter for default): "
if "%commit_message%"=="" (
    set commit_message="Update AEGIS Personal Cognitive Advisor - %date% %time%"
)

echo.
echo [INFO] Committing changes with message: %commit_message%
git commit -m %commit_message%

if %errorlevel% neq 0 (
    echo [ERROR] Commit failed!
    pause
    exit /b 1
)

echo.
echo [INFO] Pushing to GitHub...
git push origin main

if %errorlevel% neq 0 (
    echo [ERROR] Push failed!
    echo This might be because:
    echo 1. No remote repository is configured
    echo 2. Authentication issues
    echo 3. Network problems
    echo.
    echo To set up remote repository, run:
    echo git remote add origin https://github.com/Hhiieeuu1706/HFACS.git
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Code successfully pushed to GitHub!
echo.
echo Repository URL: https://github.com/Hhiieeuu1706/HFACS.git
echo.
pause

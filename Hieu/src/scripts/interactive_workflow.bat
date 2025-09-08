@echo off
SETLOCAL ENABLEDELAYEDEXPANSION

REM Set the project root to the directory where this batch file is located
SET "PROJECT_ROOT=%~dp0"

REM Add the project root to PYTHONPATH to ensure modules are found
SET "PYTHONPATH=!PROJECT_ROOT!;%PYTHONPATH%"

REM Change directory to the project root
CD /D "%PROJECT_ROOT%"

ECHO Starting the HFACS Interactive Workflow...
ECHO.

REM --- Clear Previous Outputs ---
ECHO Clearing previous run outputs...

REM Clear simulation_runs
IF EXIST "project_outputs\simulation_runs" (
    ECHO Deleting contents of project_outputs\simulation_runs
    for /d %%i in ("project_outputs\simulation_runs\*") do (rd /s /q "%%i")
    del /q "project_outputs\simulation_runs\*.*"
)
md "project_outputs\simulation_runs" >nul 2>&1

REM Clear analysis_charts
IF EXIST "project_outputs\analysis_charts" (
    ECHO Deleting contents of project_outputs\analysis_charts
    for /d %%i in ("project_outputs\analysis_charts\*") do (rd /s /q "%%i")
    del /q "project_outputs\analysis_charts\*.*"
)
md "project_outputs\analysis_charts" >nul 2>&1

REM Clear test
IF EXIST "project_outputs\test" (
    ECHO Deleting contents of project_outputs\test
    for /d %%i in ("project_outputs\test\*") do (rd /s /q "%%i")
    del /q "project_outputs\test\*.*"
)
md "project_outputs\test" >nul 2>&1

ECHO Previous outputs cleared.
ECHO.
REM --- End Clear Outputs ---


REM --- Check and Install Python Dependencies ---
ECHO Checking Python dependencies...

SET "REQUIRED_PACKAGES=pandas google-cloud-aiplatform openpyxl"

FOR %%P IN (%REQUIRED_PACKAGES%) DO (
    ECHO.
    ECHO Checking for %%P...
    python -c "import %%P" >nul 2>&1
    IF ERRORLEVEL 1 (
        ECHO %%P not found. Installing...
        pip install %%P
        IF ERRORLEVEL 1 (
            ECHO ERROR: Failed to install %%P. Please check your internet connection or Python installation.
            PAUSE
            EXIT /B 1
        ) ELSE (
            ECHO %%P installed successfully.
        )
    ) ELSE (
        ECHO %%P is already installed.
    )
)
ECHO All required Python dependencies are checked.
ECHO.
REM --- End Dependency Check ---

python run_interactive_workflow.py

ECHO.
ECHO Workflow finished.
PAUSE
ENDLOCAL
@echo off
SETLOCAL ENABLEDELAYEDEXPANSION
REM Set the project root to the main project directory
SET "PROJECT_ROOT=%~dp0..\"
REM Add the project root to PYTHONPATH to ensure modules are found
SET "PYTHONPATH=!PROJECT_ROOT!;%PYTHONPATH%"
REM Change directory to the project root
CD /D "%PROJECT_ROOT%"
ECHO Starting HFACS Expert Panel Analysis for Excel Data...
ECHO.
python _archive\run_excel_panel_analysis.py
ECHO.
ECHO Analysis finished.
PAUSE
ENDLOCAL

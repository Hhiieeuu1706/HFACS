@echo off
set PYTHONPATH=%~dp0src;%PYTHONPATH%

echo --- Starting Live Dashboard Web Server in a new window... ---
start "Web Dashboard" python src\web_dashboard\app.py

echo --- Starting Automated Console Analysis ---
python src\scripts\run_interactive_workflow.py --sync

pause
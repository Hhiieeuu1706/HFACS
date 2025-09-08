@echo off
REM ==============================================================================
REM ==                 AVIATION SCENARIO SIMULATOR RUNNER (v8)                  ==
REM ==============================================================================
REM ==  FIXES:                                                                ==
REM ==  - This is the definitive version. It exclusively controls the         ==
REM ==    PYTHONPATH and uses the standard Python module execution flag (-m). ==
REM ==    This separates responsibilities cleanly.                            ==
REM ==============================================================================

SETLOCAL

REM *** BƯỚC 1 (CỐT LÕI): Xác định và thiết lập đường dẫn gốc tuyệt đối ***
REM %~dp0 là đường dẫn đến thư mục chứa file .bat này.
REM Đường dẫn gốc của project (PROJECT_ROOT) là thư mục CHA của thư mục này.
pushd "%~dp0\.."
SET "PROJECT_ROOT=%CD%"
popd
SET "PYTHONPATH=%PROJECT_ROOT%"

REM --- Cấu hình ---
SET PYTHON_EXE=python

REM --- Xử lý Input ---
IF "%~1"=="" (
    echo [ERROR] Ban chua chi dinh ten kich ban can chay.
    echo.
    echo Vui long keo va tha mot file .json tu thu muc 'scenarios' vao file nay,
    echo hoac chay tu command line nhu sau:
    echo   run_simulator.bat ten_kich_ban
    echo.
    echo Cac kich ban co san:
    dir /b "data_input_simulator\scenarios\*.json" | findstr /R ".json"
    echo.
    pause
    GOTO :EOF
)

SET SCENARIO_NAME=%~n1

REM Tạo thư mục output
SET "YYYY=%date:~10,4%"
SET "MM=%date:~4,2%"
SET "DD=%date:~7,2%"
SET "HH=%time:~0,2%"
SET "MIN=%time:~3,2%"
SET "SEC=%time:~6,2%"
if "%HH:~0,1%"==" " set HH=0%HH:~1,1%
SET TIMESTAMP=%YYYY%-%MM%-%DD%_%HH%%MIN%%SEC%
SET OUTPUT_DIR=project_outputs\simulation_runs\%SCENARIO_NAME%_%TIMESTAMP%

REM --- Thực thi Script Python ---
echo ==============================================================================
echo [INFO] Chuan bi chay mo phong...
echo [INFO] Kich ban      : %SCENARIO_NAME%
echo [INFO] Thu muc output: %OUTPUT_DIR%
echo [INFO] PYTHONPATH set to: %PYTHONPATH%
echo ==============================================================================
echo.

echo DEBUG: About to execute Python command.
echo DEBUG: PYTHON_EXE: %PYTHON_EXE%
echo DEBUG: SCENARIO_NAME: %SCENARIO_NAME%
echo DEBUG: OUTPUT_DIR: %OUTPUT_DIR%
echo DEBUG: PROJECT_ROOT: %PROJECT_ROOT%
pause

REM *** BƯỚC 2 (CỐT LÕI): Chạy Python như một module. Python sẽ dùng PYTHONPATH ở trên. ***
%PYTHON_EXE% -m data_input_simulator.main_simulator --scenario "%SCENARIO_NAME%" --output "%OUTPUT_DIR%" --project_id "your-gcp-project-id" --location "us-central1" --credentials "%PROJECT_ROOT%\gcloud_credentials.json"

pause

REM --- Hoàn tất ---
echo.
echo ==============================================================================
echo [SUCCESS] Mo phong da hoan tat!
echo [SUCCESS] Kiem tra ket qua trong thu muc: %OUTPUT_DIR%
echo ==============================================================================
echo.
pause
ENDLOCAL
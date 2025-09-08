@echo off
REM ==============================================================================
REM ==                 FULL SYSTEM DEMO RUNNER (RANDOM SCENARIO)                ==
REM ==============================================================================
REM ==                                                                        ==
REM ==  Chuc nang:                                                            ==
REM ==  - Double-click de chay.                                               ==
REM ==  - Tu dong thuc thi mot buoi demo hoan chinh (Sense-Detect-Explain-Act) ==
REM ==    voi mot kich ban loi duoc chon NGAU NHIEN.                           ==
REM ==                                                                        ==
REM ==============================================================================

SETLOCAL

REM --- Thiet lap moi truong ---
REM Thay đổi thư mục làm việc về vị trí của file .bat này (thư mục gốc)
cd /d "%~dp0"
SET PYTHON_EXE=python

REM --- Thuc thi Script Python chinh ---
echo ==============================================================================
echo [INFO] KHOI DONG HE THONG PHAN TICH RUI RO HANG KHONG
echo [INFO] Che do: Demo hoan chinh voi kich ban ngau nhien
echo ==============================================================================
echo.

REM Goi main.py o che do 'demo' voi kich ban 'random' (la mac dinh)
%PYTHON_EXE% main.py demo --scenario random

REM --- Hoan tat ---
echo.
echo ==============================================================================
echo [SUCCESS] BUOI DEMO DA HOAN TAT!
echo ==============================================================================
echo.
pause
ENDLOCAL
@echo off
title Aviation Accident Classifier

echo --- Chuan bi chay chuong trinh phan loai tai nan ---
echo.

REM --- Buoc 1: Cai dat cac thu vien can thiet ---
echo [1/4] Dang cai dat cac thu vien...
pip install pandas openpyxl google-generativeai tqdm matplotlib
echo    -> Da cai dat xong.

echo.

REM --- Buoc 2: Chuyen den dung thu muc cua project ---
echo [2/4] Dang di chuyen den thu muc project...
G:
cd "\.shortcut-targets-by-id\1xir7002UReuNXtVU9X7CNhLq45od7PhU\Python Project\Hieu\_archive"
echo    -> Da den dung thu muc.

echo.

REM --- Buoc 3: Kiem tra Python va chay script ---
echo [3/4] Dang tim va chay script 'run_classification.py'...
python run_classification.py

echo.

REM --- Buoc 4: Hoan tat ---
echo [4/4] Chuong trinh da chay xong.
echo Nhan phim bat ky de dong cua so nay.
pause
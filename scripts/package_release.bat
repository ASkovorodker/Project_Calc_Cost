@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ============================================================
REM package_release.bat — оркестратор сборки calculator.exe
REM
REM Workflow:
REM   1. Проверка наличия артефактов
REM   2. Очистка предыдущей сборки
REM   3. pyinstaller calculator.spec --noconfirm
REM   4. Копирование template, data, run.bat рядом с exe
REM   5. Итоговый отчёт
REM
REM Запуск из корня репо:
REM     scripts\package_release.bat
REM ============================================================

pushd "%~dp0\.."

echo ============================================================
echo   PACKAGE RELEASE
echo ============================================================
echo Корень проекта: %CD%
echo.

REM ----- 1. Проверка артефактов -----
echo [1/5] Проверка артефактов...

if not exist "data\database.db" (
    echo FAIL: нет data\database.db
    echo       Запустите: python scripts\build_release.py
    popd
    exit /b 1
)
if not exist "data\index\equipment.index" (
    echo FAIL: нет data\index\equipment.index
    echo       Запустите: python scripts\build_release.py
    popd
    exit /b 1
)
if not exist "data\index\equipment_meta.json" (
    echo FAIL: нет data\index\equipment_meta.json
    echo       Запустите: python scripts\build_release.py
    popd
    exit /b 1
)
if not exist "models\multilingual-e5-base" (
    echo FAIL: нет models\multilingual-e5-base
    echo       Запустите: python scripts\download_model.py
    popd
    exit /b 1
)
if not exist "template\template.xlsx" (
    echo FAIL: нет template\template.xlsx
    popd
    exit /b 1
)
if not exist "calculator.spec" (
    echo FAIL: нет calculator.spec
    popd
    exit /b 1
)
echo   OK: все артефакты на месте.

REM ----- 2. Очистка прошлой сборки -----
echo.
echo [2/5] Очистка прошлой сборки...
if exist "dist\calculator" rmdir /s /q "dist\calculator"
if exist "build" rmdir /s /q "build"
echo   OK

REM ----- 3. PyInstaller -----
echo.
echo [3/5] PyInstaller (это займёт несколько минут)...
pyinstaller calculator.spec --noconfirm
if errorlevel 1 (
    echo FAIL: PyInstaller вернул ошибку
    popd
    exit /b 1
)
if not exist "dist\calculator\calculator.exe" (
    echo FAIL: dist\calculator\calculator.exe не создан
    popd
    exit /b 1
)
echo   OK: calculator.exe собран

REM ----- 4. Копирование артефактов рядом с exe -----
echo.
echo [4/5] Копирование template, data, run.bat...
xcopy /e /i /y /q "template" "dist\calculator\template" > nul
xcopy /i /y /q "data\database.db" "dist\calculator\data\" > nul
xcopy /e /i /y /q "data\index" "dist\calculator\data\index" > nul

if not exist "dist\calculator\data\input"  mkdir "dist\calculator\data\input"
if not exist "dist\calculator\data\output" mkdir "dist\calculator\data\output"
if not exist "dist\calculator\data\logs"   mkdir "dist\calculator\data\logs"

copy /y "scripts\run.bat" "dist\calculator\run.bat" > nul
echo   OK

REM ----- 5. Итоговый отчёт -----
echo.
echo [5/5] Итог:
echo.
echo   Bundle:  %CD%\dist\calculator\
echo   Запуск:  dist\calculator\run.bat  (двойной клик)
echo.
echo Содержимое dist\calculator\:
dir /b "dist\calculator"

echo.
echo ============================================================
echo   ГОТОВО
echo ============================================================

popd
endlocal
exit /b 0

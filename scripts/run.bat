@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo === Запуск Project_Calc ===
echo.

calculator.exe

echo.
echo === Готово ===
echo Результат: data\output\result.xlsx
echo Логи:      data\logs\log.txt
echo.
pause

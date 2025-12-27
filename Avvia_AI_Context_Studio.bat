@echo off
title AI Context Studio

echo.
echo   AI Context Studio v2.1.0
echo.
cd /d "%~dp0"

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRORE: Python non trovato!
    pause
    exit /b 1
)

echo [OK] Avvio applicazione...

REM SOLUZIONE: Usiamo esplicitamente pythonw (windowless) invece di affidarci all'estensione file
start "" pythonw "%~dp0launcher.pyw"

REM Chiude questa finestra nera dopo 1 secondo
timeout /t 1 >nul
exit
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
    echo Installa Python da https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python trovato

REM Installa dipendenze se mancanti
python -c "import customtkinter" >nul 2>&1 || pip install customtkinter -q
python -c "import google.generativeai" >nul 2>&1 || pip install google-generativeai -q
python -c "import cryptography" >nul 2>&1 || pip install cryptography -q

echo [OK] Dipendenze verificate
echo.
echo Avvio applicazione...

REM Avvia direttamente il file .pyw (Windows lo esegue senza console)
start "" "%~dp0launcher.pyw"

timeout /t 1 >nul

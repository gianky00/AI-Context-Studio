@echo off
chcp 65001 >nul
REM ══════════════════════════════════════════════════════════════════════════════
REM  AI Context Studio - Windows Launcher
REM  Autore: Giancarlo Allegretti
REM ══════════════════════════════════════════════════════════════════════════════
REM  Questo script:
REM  1. Verifica che Python sia installato
REM  2. Installa automaticamente le dipendenze se mancanti
REM  3. Avvia l'applicazione GUI
REM ══════════════════════════════════════════════════════════════════════════════

title AI Context Studio - Avvio

echo.
echo ══════════════════════════════════════════════════════════════════════════════
echo   AI Context Studio v1.1.0
echo   by Giancarlo Allegretti
echo ══════════════════════════════════════════════════════════════════════════════
echo.

REM Verifica Python
echo [1/3] Verifica installazione Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ❌ ERRORE: Python non trovato!
    echo    Installa Python da https://www.python.org/downloads/
    echo    Assicurati di selezionare "Add Python to PATH" durante l'installazione.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo    ✅ Python %PYVER% trovato

REM Verifica e installa dipendenze
echo.
echo [2/3] Verifica dipendenze...

REM Controlla customtkinter
python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo    📦 Installazione customtkinter...
    pip install customtkinter --quiet
    if errorlevel 1 (
        echo    ❌ Errore installazione customtkinter
        pause
        exit /b 1
    )
    echo    ✅ customtkinter installato
) else (
    echo    ✅ customtkinter presente
)

REM Controlla google-generativeai
python -c "import google.generativeai" >nul 2>&1
if errorlevel 1 (
    echo    📦 Installazione google-generativeai...
    pip install google-generativeai --quiet
    if errorlevel 1 (
        echo    ❌ Errore installazione google-generativeai
        pause
        exit /b 1
    )
    echo    ✅ google-generativeai installato
) else (
    echo    ✅ google-generativeai presente
)

echo.
echo [3/3] Avvio AI Context Studio...
echo.
echo ══════════════════════════════════════════════════════════════════════════════
echo.

REM Avvia l'applicazione (senza mostrare la console)
set PYTHONPATH=%~dp0src;%PYTHONPATH%

if not exist "%~dp0src\ai_context_studio\main.py" (
    echo.
    echo ❌ ERRORE: File principale non trovato in src\ai_context_studio\main.py
    pause
    exit /b 1
)

python -m ai_context_studio.main
pause

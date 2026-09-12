@echo off
REM Social Wars - prepara tudo do zero, com um clique duplo.
title Preparar Social Wars
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] Python 3 nao encontrado.
    echo      Baixe em https://python.org e marque "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

%PY% preparar.py %*
echo.
pause

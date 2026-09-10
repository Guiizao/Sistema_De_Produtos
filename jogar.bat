@echo off
REM Social Wars - inicia o jogo com um clique duplo.
title Social Wars
cd /d "%~dp0"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

%PY% -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [+] Instalando as dependencias pela primeira vez...
    echo.
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  [!] Nao consegui instalar as dependencias.
        echo      Instale o Python 3 em https://python.org e marque "Add to PATH".
        pause
        exit /b 1
    )
)

%PY% play.py %*
if errorlevel 1 pause

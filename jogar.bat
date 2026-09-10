@echo off
REM Social Wars - inicia o jogo com um clique duplo.
REM NAO precisa de administrador: as dependencias vao para um ambiente
REM virtual dentro desta pasta (.venv), nunca no Python do sistema.
setlocal
title Social Wars
cd /d "%~dp0"

set "REQS=requirements.txt"
if exist "requirements-swboost.txt" set "REQS=requirements-swboost.txt"

set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [!] Python 3 nao encontrado.
    echo      Baixe em https://python.org e, no instalador, escolha
     echo      "Install for me only" - essa opcao NAO pede administrador.
    echo      Marque tambem "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

REM Ambiente virtual local: dispensa administrador e nao mexe no Python do PC.
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    %PY% -c "import flask, waitress" >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  [+] Preparando o ambiente pela primeira vez ^(sem administrador^)...
        echo.
        %PY% -m venv .venv
        if errorlevel 1 (
            echo  [!] Nao consegui criar o .venv. Tentando instalar so para voce...
            %PY% -m pip install --user -r %REQS%
        ) else (
            set "PY=.venv\Scripts\python.exe"
            .venv\Scripts\python.exe -m pip install --upgrade pip
            .venv\Scripts\python.exe -m pip install -r %REQS%
        )
    )
)

%PY% play.py %*
if errorlevel 1 pause

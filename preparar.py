#!/usr/bin/env python3
"""Deixa tudo pronto para jogar, do zero, em um comando.

    python preparar.py

Faz, em ordem:

1. confere o Python;
2. acha ou baixa o Social Wars (o `git clone` do projeto original);
3. copia o SW Boost para dentro da pasta do jogo;
4. cria o ambiente virtual e instala as dependencias (para a primeira
   partida nao ter espera);
5. cria um atalho na Area de Trabalho (Windows);
6. diz o que falta - normalmente so o navegador com Flash.

Nada exige administrador: o ambiente virtual e o atalho ficam na pasta do
usuario.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swboost.gamedir import BoostError, locate_game_dir  # noqa: E402

RAIZ = os.path.dirname(os.path.abspath(__file__))
REPO_JOGO = "https://github.com/AcidCaos/socialwarriors.git"
ZIP_JOGO = "https://github.com/AcidCaos/socialwarriors/archive/refs/heads/main.zip"
PASTA_PADRAO = "socialwarriors"


def passo(numero: int, titulo: str) -> None:
    print(f"\n{'=' * 62}\n  PASSO {numero} - {titulo}\n{'=' * 62}")


def perguntar_sim(pergunta: str, padrao: bool = True) -> bool:
    sufixo = "[S/n]" if padrao else "[s/N]"
    try:
        resposta = input(f"  {pergunta} {sufixo} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if not resposta:
        return padrao
    return resposta[0] in "sy"


# --------------------------------------------------------------------------
# 2. achar ou baixar o jogo
# --------------------------------------------------------------------------


def baixar_jogo(destino: str) -> str | None:
    if not shutil.which("git"):
        print("  [!] O git nao esta instalado, entao nao da para baixar automaticamente.")
        print("\n      Duas saidas:")
        print("      1) instale o git em https://git-scm.com/downloads e rode de novo")
        print("      2) baixe o jogo pelo navegador (~1,4 GB), extraia, e rode")
        print("         este preparar.py de novo apontando para a pasta:")
        print(f"         {ZIP_JOGO}")
        return None

    print(f"  Baixando o jogo em: {destino}")
    print("  Sao ~1,4 GB. Vai demorar - e normal.\n")
    resultado = subprocess.run(["git", "clone", "--depth", "1", REPO_JOGO, destino])
    if resultado.returncode != 0:
        print("\n  [!] O download falhou.")
        return None
    return destino


def obter_pasta_do_jogo(indicada: str | None) -> str | None:
    if indicada:
        try:
            return locate_game_dir(indicada)
        except BoostError as exc:
            print(f"  [!] {exc}")
            return None

    try:
        encontrada = locate_game_dir()
        print(f"  Jogo encontrado em: {encontrada}")
        if perguntar_sim("Usar esta pasta?"):
            return encontrada
    except BoostError:
        print("  Ainda nao encontrei o jogo por aqui.")

    print("\n  Onde esta o Social Wars?")
    print("  - Enter para baixar agora (~1,4 GB)")
    print("  - ou arraste a pasta do jogo para esta janela e aperte Enter\n")
    try:
        resposta = input("  Caminho: ").strip().strip("\"'").rstrip("\\/")
    except (EOFError, KeyboardInterrupt):
        return None

    if resposta:
        try:
            return locate_game_dir(resposta)
        except BoostError as exc:
            print(f"  [!] {exc}")
            return None

    return baixar_jogo(os.path.join(os.path.dirname(RAIZ), PASTA_PADRAO))


# --------------------------------------------------------------------------
# 4. ambiente virtual
# --------------------------------------------------------------------------


def preparar_venv(pasta_jogo: str) -> str | None:
    """Cria o .venv e instala as dependencias. Devolve o python do ambiente."""
    venv = os.path.join(pasta_jogo, ".venv")
    binario = os.path.join(venv, "Scripts" if os.name == "nt" else "bin",
                           "python.exe" if os.name == "nt" else "python")

    if not os.path.isfile(binario):
        print("  Criando o ambiente virtual (nao mexe no Python do sistema)...")
        if subprocess.run([sys.executable, "-m", "venv", venv]).returncode != 0:
            print("  [!] Nao consegui criar o .venv.")
            return None

    requisitos = os.path.join(pasta_jogo, "requirements-swboost.txt")
    if not os.path.isfile(requisitos):
        requisitos = os.path.join(RAIZ, "requirements.txt")

    print("  Instalando Flask, waitress, jsonpatch e requests...")
    subprocess.run([binario, "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    if subprocess.run([binario, "-m", "pip", "install", "-r", requisitos]).returncode != 0:
        print("  [!] Alguma dependencia falhou.")
        return None
    return binario


# --------------------------------------------------------------------------
# 5. atalho
# --------------------------------------------------------------------------


def criar_atalho(pasta_jogo: str) -> str | None:
    """Cria um atalho na Area de Trabalho do Windows, sem bibliotecas extras."""
    if os.name != "nt":
        return None

    area = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.isdir(area):
        area = os.path.join(os.path.expanduser("~"), "Area de Trabalho")
    if not os.path.isdir(area):
        return None

    atalho = os.path.join(area, "Social Wars.lnk")
    alvo = os.path.join(pasta_jogo, "jogar.bat")
    icone = os.path.join(pasta_jogo, "build", "icon.ico")

    # O WScript.Shell ja vem no Windows: cria .lnk sem instalar nada.
    script = f'''Set shell = CreateObject("WScript.Shell")
Set atalho = shell.CreateShortcut("{atalho}")
atalho.TargetPath = "{alvo}"
atalho.WorkingDirectory = "{pasta_jogo}"
atalho.Description = "Social Wars"
'''
    if os.path.isfile(icone):
        script += f'atalho.IconLocation = "{icone}"\n'
    script += "atalho.Save\n"

    caminho_vbs = os.path.join(pasta_jogo, "_atalho.vbs")
    try:
        with open(caminho_vbs, "w", encoding="mbcs", errors="replace") as handle:
            handle.write(script)
        subprocess.run(["cscript", "//nologo", caminho_vbs], timeout=30,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.remove(caminho_vbs)
        except OSError:
            pass

    return atalho if os.path.isfile(atalho) else None


# --------------------------------------------------------------------------


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("jogo", nargs="?", help="pasta do Social Wars, se ja tiver")
    parser.add_argument("--sem-atalho", action="store_true")
    args = parser.parse_args(argv)

    print("\n  Preparando o Social Wars para jogar.")
    print("  Pode deixar rodando - ele avisa quando terminar.")

    passo(1, "Python")
    print(f"  Python {sys.version.split()[0]} em {sys.executable}")
    if sys.version_info < (3, 8):
        print("  [!] Precisa ser Python 3.8 ou mais novo.")
        return 1

    passo(2, "O jogo")
    pasta_jogo = obter_pasta_do_jogo(args.jogo)
    if not pasta_jogo:
        print("\n  [!] Sem a pasta do jogo nao da para continuar.")
        return 1
    pasta_jogo = os.path.abspath(pasta_jogo)
    print(f"  OK: {pasta_jogo}")

    passo(3, "Aplicando as melhorias")
    import instalar  # noqa: E402  (depois do sys.path estar pronto)

    if instalar.main([pasta_jogo, "--force"]) != 0:
        return 1

    passo(4, "Dependencias")
    binario = preparar_venv(pasta_jogo)
    if not binario:
        print("  [!] Sem as dependencias o jogo nao sobe. Veja o erro acima.")
        return 1
    print("  OK")

    passo(5, "Atalho")
    atalho = None if args.sem_atalho else criar_atalho(pasta_jogo)
    print(f"  Criado: {atalho}" if atalho else "  (pulado)")

    passo(6, "Conferindo")
    subprocess.run([binario, os.path.join(pasta_jogo, "play.py"), "--check"],
                   cwd=pasta_jogo)

    print(f"\n{'=' * 62}")
    print("  TUDO PRONTO")
    print(f"{'=' * 62}\n")
    if atalho:
        print("  Para jogar: clique duas vezes no atalho 'Social Wars' da")
        print("  Area de Trabalho.\n")
    else:
        print(f"  Para jogar, entre em:\n    {pasta_jogo}")
        print("  e rode o jogar.bat (Windows) ou ./jogar.sh (Linux)\n")
    print("  Se a linha 'Flash' acima disse que nao encontrou nada, instale o")
    print("  FlashBrowser:")
    print("    https://github.com/radubirsan/FlashBrowser/releases/latest")
    print("  ou coloque um navegador/Flash Player portatil em:")
    print(f"    {os.path.join(pasta_jogo, 'browser')}\n")
    print(f"  Esta pasta aqui ({os.path.basename(RAIZ)}) ja cumpriu o papel")
    print("  e pode ser apagada.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

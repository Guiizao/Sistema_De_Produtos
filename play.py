#!/usr/bin/env python3
"""Social Wars - lancador unico.

Sobe o servidor do jogo, espera ele responder e ja abre um navegador com
Flash na tela certa. Sem terminal aberto de um lado e navegador do outro.

Uso rapido:

    python play.py                 # inicia tudo e entra no ultimo save
    python play.py --fps 60        # modo turbo (leia ANALISE_TECNICA.md)
    python play.py --check         # so diagnostica a instalacao
    python play.py --list-browsers # mostra os navegadores Flash encontrados
"""

from __future__ import annotations

import argparse
import glob
import os
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swboost import __version__, boost, browsers, settings as settings_module  # noqa: E402

BANNER = r"""
  ____             _       _  __        __
 / ___|  ___   ___(_) __ _| | \ \      / /_ _ _ __ ___
 \___ \ / _ \ / __| |/ _` | |  \ \ /\ / / _` | '__/ __|
  ___) | (_) | (__| | (_| | |   \ V  V / (_| | |  \__ \
 |____/ \___/ \___|_|\__,_|_|    \_/\_/ \__,_|_|  |___/
"""


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="play.py",
        description="Lancador do Social Wars com melhorias de desempenho.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--game-dir", help="pasta do jogo (a que contem server.py)")
    parser.add_argument("--host", help="endereco de escuta (padrao 127.0.0.1)")
    parser.add_argument("--port", type=int, help="porta do servidor (padrao 5055)")
    parser.add_argument(
        "--fps",
        type=int,
        help="taxa de quadros do jogo: 0 mantem os 30 originais; "
             "60 e 120 aceleram o jogo inteiro na mesma proporcao",
    )
    parser.add_argument("--browser", help="caminho do navegador com Flash, ou 'none'")
    parser.add_argument("--no-browser", action="store_true", help="nao abrir navegador")
    parser.add_argument("--no-quickplay", action="store_true",
                        help="abrir a tela de login em vez de entrar no ultimo save")
    parser.add_argument("--projector", action="store_true",
                        help="abrir com o Flash Player standalone, sem navegador nenhum")
    parser.add_argument("--server", choices=("auto", "waitress", "flask"),
                        help="servidor HTTP a usar")
    parser.add_argument("--verbose", action="store_true",
                        help="mostrar todo o log (desliga o filtro de linhas repetidas)")
    parser.add_argument("--check", action="store_true",
                        help="diagnosticar a instalacao e sair")
    parser.add_argument("--list-browsers", action="store_true",
                        help="listar os navegadores com Flash encontrados e sair")
    parser.add_argument("--write-config", action="store_true",
                        help="gravar um swboost.ini com os padroes e sair")
    parser.add_argument("--exe", nargs="?", const="auto",
                        help="usar o executavel do bundle (release 0.02a) em vez do codigo-fonte")
    parser.add_argument("--version", action="version", version=f"SW Boost {__version__}")
    return parser.parse_args(argv)


def build_settings(args: argparse.Namespace, config_dir: str):
    overrides = {
        "host": args.host,
        "port": args.port,
        "fps": args.fps,
        "server": args.server,
    }
    if args.browser:
        overrides["browser"] = args.browser
    if args.no_browser:
        overrides["open_browser"] = False
    if args.no_quickplay:
        overrides["quickplay"] = False
    if args.verbose:
        overrides["quiet"] = False
    return settings_module.load(config_dir, {k: v for k, v in overrides.items() if v is not None})


def projector_url(host: str, port: int) -> str | None:
    """Pede ao servidor a URL que o Flash Player standalone abre direto."""
    endereco = f"http://{host}:{port}/swboost/projector"
    try:
        with urllib.request.urlopen(endereco, timeout=15) as resposta:
            return json.loads(resposta.read().decode("utf-8")).get("url")
    except (urllib.error.URLError, ValueError, OSError):
        return None


def como_iniciar() -> str:
    """Como o jogador roda isto de novo - muda se estamos num executavel."""
    if getattr(sys, "frozen", False):
        return os.path.basename(sys.executable)
    return "python play.py"


def wait_for_server(host: str, port: int, timeout: float = 90.0) -> bool:
    """Espera a porta aceitar conexoes."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.25)
    return False


# --------------------------------------------------------------------------
# diagnostico
# --------------------------------------------------------------------------


def run_check(args: argparse.Namespace, cfg) -> int:
    print(BANNER)
    print(f"  SW Boost {__version__} - diagnostico\n")
    problems = 0

    print(f"  Python .................. {sys.version.split()[0]}")

    try:
        game_dir = boost.locate_game_dir(args.game_dir)
        print(f"  Pasta do jogo ........... {game_dir}")
    except boost.BoostError as exc:
        print(f"  Pasta do jogo ........... NAO ENCONTRADA\n\n{exc}")
        return 1

    assets = os.path.join(game_dir, "assets")
    if os.path.isdir(assets):
        flash_dir = os.path.join(assets, "flash")
        count = len(glob.glob(os.path.join(flash_dir, "*.swf"))) if os.path.isdir(flash_dir) else 0
        print(f"  Assets .................. OK ({count} SWF em assets/flash)")
        if count == 0:
            print("      [!] Nenhum SWF do jogo encontrado.")
            problems += 1
    else:
        print("  Assets .................. FALTANDO (pasta assets/ nao existe)")
        problems += 1

    for module, required in (("flask", True), ("jsonpatch", True),
                             ("waitress", False), ("requests", False)):
        try:
            __import__(module)
            print(f"  {module:<10}............... OK")
        except ImportError:
            label = "FALTANDO" if required else "ausente (opcional)"
            print(f"  {module:<10}............... {label}")
            if required:
                problems += 1

    from swboost import saves as saves_module
    problemas = saves_module.unsafe_saves_entries(os.path.join(game_dir, "saves"))
    if problemas:
        print("  Pasta saves/ ........... PROBLEMA")
        for entry in problemas:
            print(f"      [!] saves/{entry} e uma pasta; o jogo tenta abri-la como save")
        print("      Mova-a para fora de saves/.")
        problems += 1
    else:
        print("  Pasta saves/ ........... OK")

    free = boost.port_is_free(cfg.host, cfg.port)
    print(f"  Porta {cfg.port} .............. {'livre' if free else 'EM USO'}")
    if not free:
        print("      [!] Outro processo ja usa essa porta (o jogo ja esta aberto?).")
        problems += 1

    found = browsers.discover(game_dir)
    if found:
        print(f"  Flash ................... {found[0].describe()}")
        for extra in found[1:]:
            print(f"                            (tambem: {extra.describe()})")
        if found[0].kind == "projector":
            print("      E um Flash Player standalone: abre o jogo sem navegador.")
    else:
        print("  Flash ................... nenhum encontrado")
        print("      Sem permissao de administrador? Use o Flash Player standalone:")
        print("      e um unico executavel, nao instala nada.")
        print(f"      Coloque-o em {os.path.join(game_dir, 'browser')}/ e rode de novo.")
        print("      Detalhes em SWBOOST.md, secao 'Sem permissao de administrador'.")

    print()
    if problems:
        print(f"  {problems} problema(s) encontrado(s).")
    else:
        print(f"  Tudo pronto. Rode: {como_iniciar()}")
    return 1 if problems else 0


# --------------------------------------------------------------------------
# modo bundle (executavel da release 0.02a)
# --------------------------------------------------------------------------


def find_executable(game_dir: str) -> str | None:
    patterns = ("social-warriors*.exe", "social-warriors*", "*.exe")
    for pattern in patterns:
        for path in sorted(glob.glob(os.path.join(game_dir, pattern))):
            if os.path.isfile(path) and os.access(path, os.X_OK | os.R_OK):
                return path
    return None


def run_bundle(args: argparse.Namespace, cfg) -> int:
    """Modo compatibilidade: sobe o executavel pronto e abre o navegador.

    Aqui o servidor e o binario congelado da release, entao as melhorias de
    servidor (cache, gzip, saves atomicos) nao se aplicam - apenas a parte de
    inicializacao com um clique.
    """
    game_dir = os.path.abspath(args.game_dir or os.getcwd())
    exe = args.exe if args.exe and args.exe != "auto" else find_executable(game_dir)
    if not exe:
        print("[!] Nao encontrei o executavel do jogo nesta pasta.")
        return 1

    print(f"[+] Iniciando {os.path.basename(exe)}...")
    process = subprocess.Popen([exe], cwd=os.path.dirname(exe) or ".")

    url = f"http://{cfg.host}:{cfg.port}/"
    if not wait_for_server(cfg.host, cfg.port):
        print("[!] O servidor nao respondeu a tempo.")
        process.terminate()
        return 1

    if cfg.open_browser:
        browser = browsers.resolve(cfg.browser, game_dir)
        print(f"[+] Abrindo {url} em: {browsers.open_url(url, browser)}")
    else:
        print(f"[+] Servidor pronto em {url}")

    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
    return 0


# --------------------------------------------------------------------------
# principal
# --------------------------------------------------------------------------


def main(argv=None) -> int:
    args = parse_args(argv)
    config_dir = os.path.dirname(os.path.abspath(__file__))

    if args.write_config:
        print(f"[+] Configuracao gravada em: {settings_module.write_default(config_dir)}")
        return 0

    cfg = build_settings(args, config_dir)

    if args.list_browsers:
        try:
            game_dir = boost.locate_game_dir(args.game_dir)
        except boost.BoostError:
            game_dir = os.getcwd()
        found = browsers.discover(game_dir)
        if not found:
            print("Nenhum navegador com Flash encontrado.")
            return 1
        for candidate in found:
            print(f"  [{candidate.kind}] {candidate.describe()}")
        return 0

    if args.check:
        return run_check(args, cfg)

    if args.exe:
        return run_bundle(args, cfg)

    if not boost.port_is_free(cfg.host, cfg.port):
        print(f"[!] A porta {cfg.port} ja esta em uso. O jogo ja esta aberto?")
        print(f"    Use --port OUTRA para subir em outra porta.")
        return 1

    print(BANNER)
    print(f"  SW Boost {__version__}\n")

    try:
        boosted = boost.apply(cfg, args.game_dir)
    except boost.BoostError as exc:
        print(f"[!] {exc}")
        return 1

    path = "/jogar" if cfg.quickplay else "/"
    url = f"http://{cfg.host}:{cfg.port}{path}"

    thread = threading.Thread(target=boost.serve, args=(boosted,), daemon=True)
    thread.start()

    if not wait_for_server(cfg.host, cfg.port):
        print("[!] O servidor nao subiu a tempo.")
        return 1

    print()
    print(f"  Servidor ....... http://{cfg.host}:{cfg.port}/")
    print(f"  Taxa de quadros  {cfg.fps or 30} fps" + ("  (turbo)" if cfg.fps else "  (original)"))
    print(f"  Cache de assets  {cfg.cache_max_age} s")

    if cfg.open_browser:
        browser = browsers.resolve(cfg.browser, boosted.game_dir)
        usar_projector = args.projector or (browser is not None and browser.kind == "projector")

        if usar_projector:
            direto = projector_url(cfg.host, cfg.port)
            if direto is None:
                print("\n  [!] Ainda nao existe nenhuma vila. Crie uma primeiro:")
                print(f"      http://{cfg.host}:{cfg.port}/new.html")
            elif browser is None:
                print("\n  [!] Nao encontrei o Flash Player standalone.")
                print("      Coloque-o em browser/ dentro da pasta do jogo.")
                print("      Se voce ja tem um, abra este endereco nele:")
                print(f"      {direto}")
            else:
                print(f"  Flash .......... {browsers.open_url(direto, browser)}")
                print("                   (modo projector: sem navegador)")
        elif browser is None and cfg.browser.lower() == "auto":
            print("\n  [!] Nenhum navegador com Flash encontrado.")
            print("      Abra manualmente no seu navegador Flash:")
            print(f"      {url}")
        else:
            print(f"  Navegador ...... {browsers.open_url(url, browser)}")
    else:
        print(f"\n  Abra no seu navegador Flash: {url}")

    print("\n  Ctrl+C encerra o servidor.\n")

    try:
        while thread.is_alive():
            thread.join(1.0)
    except KeyboardInterrupt:
        print("\n[+] Encerrando.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

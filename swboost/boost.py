"""Montagem do servidor turbinado.

Fluxo: localizar a pasta do jogo -> importar o `server.py` original (o que
carrega saves, vilas e config) -> aplicar as melhorias sobre o objeto Flask
que ele criou -> servir.
"""

from __future__ import annotations

import logging
import os
import sys
import types
from dataclasses import dataclass

from . import console, saves, web
from .gamedir import GAME_MARKERS, BoostError, locate_game_dir, port_is_free
from .settings import Settings

BOOST_CACHE_DIRNAME = "boost_cache"

# Reexportados para quem ja importava daqui.
__all__ = ["BoostError", "Boosted", "apply", "fix_bundle_paths", "load_game",
           "locate_game_dir", "port_is_free", "serve"]


@dataclass
class Boosted:
    app: object
    game_dir: str
    settings: Settings
    info: dict


# --------------------------------------------------------------------------
# importar o servidor original
# --------------------------------------------------------------------------


def _install_requests_stub() -> bool:
    """Deixa o `import requests` do server.py funcionar sem a biblioteca.

    O `server.py` importa `requests` no topo, mas so usaria a biblioteca dentro
    de um bloco `if False:` (a variante "lite" que baixaria os assets do
    GitHub). Como `requests` nao esta no requirements.txt, uma instalacao
    limpa quebra logo no import. O stub resolve isso sem esconder problema
    nenhum: se alguem realmente usar a biblioteca, o erro aparece na hora.
    """
    try:
        import requests  # noqa: F401
        return False
    except ImportError:
        pass

    stub = types.ModuleType("requests")

    def _unavailable(*_args, **_kwargs):
        raise RuntimeError(
            "A biblioteca 'requests' nao esta instalada. "
            "Rode: pip install requests"
        )

    stub.get = _unavailable
    stub.post = _unavailable
    stub.exceptions = type("exceptions", (Exception,), {})
    sys.modules["requests"] = stub
    return True


def fix_bundle_paths(game_dir: str) -> bool:
    """Faz o `bundle.py` do jogo apontar para a pasta do jogo, nao para o exe.

    O bundle.py original comeca assim:

        TMP_BUNDLED_DIR = sys._MEIPASS if getattr(sys, 'frozen', None) else "."

    Isso e correto para o executavel oficial do projeto, que empacota os
    assets dentro de si. Mas o nosso .exe e so o lancador - os 1,4 GB de
    assets continuam na pasta do jogo, ao lado dele. Sem esta correcao, um
    build congelado procuraria assets, templates e vilas dentro da pasta
    temporaria de extracao do PyInstaller e nao acharia nada.

    Precisa rodar ANTES do `import server`, que e quem importa o bundle.
    """
    if not getattr(sys, "frozen", False):
        return False

    import bundle  # type: ignore

    bundle.TMP_BUNDLED_DIR = game_dir
    bundle.ASSETS_DIR = os.path.join(game_dir, "assets")
    bundle.STUB_DIR = os.path.join(game_dir, "stub")
    bundle.TEMPLATES_DIR = os.path.join(game_dir, "templates")
    bundle.VILLAGES_DIR = os.path.join(game_dir, "villages")
    bundle.QUESTS_DIR = os.path.join(bundle.VILLAGES_DIR, "quest")
    bundle.CONFIG_DIR = os.path.join(game_dir, "config")
    bundle.CONFIG_PATCH_DIR = os.path.join(bundle.CONFIG_DIR, "patch")
    return True


def load_game(game_dir: str):
    """Importa o `server.py` do jogo (sem iniciar o servidor de desenvolvimento).

    O `server.py` so chama `app.run()` dentro de `if __name__ == '__main__'`,
    entao importa-lo apenas monta o Flask, carrega saves, vilas e config.
    """
    os.chdir(game_dir)  # bundle.py usa caminhos relativos a partir de "."
    if game_dir not in sys.path:
        sys.path.insert(0, game_dir)

    stubbed = _install_requests_stub()
    fix_bundle_paths(game_dir)

    try:
        import server  # type: ignore
    except ImportError as exc:
        raise BoostError(
            f"Falha ao importar o servidor do jogo: {exc}\n"
            f"Instale as dependencias com: pip install -r requirements.txt"
        ) from exc

    return server, stubbed


# --------------------------------------------------------------------------
# aplicar as melhorias
# --------------------------------------------------------------------------


def apply(settings: Settings, game_dir: str | None = None) -> Boosted:
    """Carrega o jogo e instala todas as melhorias no app Flask."""
    game_dir = locate_game_dir(game_dir)

    if settings.quiet:
        console.install()

    # O load_saves() do jogo abre como JSON tudo o que estiver em saves/ e so
    # trata JSONDecodeError. Uma subpasta ali derruba o import do server.py,
    # antes de qualquer codigo nosso rodar - entao o aviso tem que vir agora.
    problemas = saves.unsafe_saves_entries(os.path.join(game_dir, "saves"))
    if problemas:
        print("[!] Ha pastas dentro de saves/ que o jogo nao consegue carregar:")
        for entry in problemas:
            print(f"      saves/{entry}")
        print("    Mova-as para fora de saves/ ou o servidor nao vai subir.\n")

    server, stubbed_requests = load_game(game_dir)

    import bundle  # type: ignore
    import engine  # type: ignore
    import get_game_config  # type: ignore
    import sessions  # type: ignore

    app = server.app
    if not app.secret_key:
        app.secret_key = "SECRET_KEY"

    assets_dir = os.path.abspath(bundle.ASSETS_DIR)
    saves_dir = os.path.abspath(bundle.SAVES_DIR)
    cache_dir = os.path.join(game_dir, BOOST_CACHE_DIRNAME)

    applied = {
        "requests_stub": stubbed_requests,
        "static_cache": web.install_static_cache(app, settings, assets_dir, cache_dir),
        "config_cache": web.install_config_cache(app, settings, get_game_config.get_game_config),
        "atomic_saves": saves.install(sessions, saves_dir, settings),
    }
    web.install_gzip(app, settings)
    chooser = web.install_quickplay(
        app, settings, sessions, os.path.join(cache_dir, "last_played.json")
    )
    web.install_projector(app, settings, sessions, engine, chooser)
    web.install_play_page(app, settings)

    info = {
        "boost": True,
        "game_dir": game_dir,
        "assets_dir": assets_dir,
        "applied": applied,
    }
    web.install_health(app, settings, info)

    # O servidor original tambem redefine o host/porta usados no play.html.
    server.host = settings.host
    server.port = settings.port

    return Boosted(app=app, game_dir=game_dir, settings=settings, info=info)


# --------------------------------------------------------------------------
# servir
# --------------------------------------------------------------------------


def serve(boosted: Boosted) -> str:
    """Sobe o servidor. Devolve o nome do backend HTTP realmente usado."""
    settings = boosted.settings

    if settings.quiet:
        logging.getLogger("werkzeug").setLevel(logging.WARNING)
        logging.getLogger("waitress").setLevel(logging.WARNING)

    backend = settings.server.lower()
    if backend in ("auto", "waitress"):
        try:
            from waitress import serve as waitress_serve
        except ImportError:
            if backend == "waitress":
                raise BoostError(
                    "waitress nao esta instalado. Rode: pip install waitress"
                )
        else:
            waitress_serve(
                boosted.app,
                host=settings.host,
                port=settings.port,
                threads=settings.threads,
                # Os assets sao arquivos grandes servidos em rajada: manter a
                # conexao viva evita reabrir socket centenas de vezes.
                channel_timeout=120,
                ident="SocialWarriors",
                _quiet=True,
            )
            return "waitress"

    boosted.app.run(
        host=settings.host,
        port=settings.port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
    return "flask"

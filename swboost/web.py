"""Camada HTTP do SW Boost.

Todas as funcoes recebem o objeto Flask que o `server.py` do jogo ja criou e
substituem as `view_functions` existentes (ou registram novas rotas). Nenhum
arquivo do projeto original e tocado.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import re
import threading
import time

from flask import Response, redirect, request, send_file, send_from_directory

from . import swf
from .settings import Settings

# Pastas cujo conteudo e servido como SWF "raiz" (o que o navegador embute).
# So esses arquivos precisam de reescrita de frame rate: um SWF carregado por
# outro SWF herda o frameRate do palco e ignora o proprio cabecalho.
ROOT_SWF_DIR = "flash/"

_MIME_ALREADY_COMPRESSED = (
    "image/",
    "audio/",
    "video/",
    "application/x-shockwave-flash",
    "application/zip",
    "font/",
)


# --------------------------------------------------------------------------
# assets estaticos: cache do navegador + frame rate sob demanda
# --------------------------------------------------------------------------


def _send_static(directory: str, path: str, max_age: int) -> Response:
    """send_from_directory compativel com Flask 1.x e 2.x/3.x."""
    try:
        response = send_from_directory(directory, path, max_age=max_age, conditional=True)
    except TypeError:  # Flask < 2.0 usava outro nome de parametro
        response = send_from_directory(directory, path, cache_timeout=max_age, conditional=True)
    return response


class SwfFrameRateCache:
    """Guarda em disco as versoes do SWF com outro frame rate.

    A reescrita e feita uma unica vez por (arquivo, fps) e reaproveitada nas
    execucoes seguintes. Se o arquivo original mudar, o cache e refeito.
    """

    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = cache_dir
        self._lock = threading.Lock()

    def get(self, source: str, fps: int) -> str:
        stat = os.stat(source)
        name = os.path.basename(source)
        stamp = f"{int(stat.st_mtime)}-{stat.st_size}"
        target = os.path.join(self.cache_dir, f"{name}.{fps}fps.{stamp}.swf")

        if os.path.isfile(target):
            return target

        with self._lock:
            if os.path.isfile(target):  # outra thread pode ter chegado antes
                return target
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(source, "rb") as handle:
                patched = swf.set_frame_rate(handle.read(), float(fps))
            tmp = target + ".tmp"
            with open(tmp, "wb") as handle:
                handle.write(patched)
            os.replace(tmp, target)

            # Limpa versoes antigas do mesmo arquivo/fps.
            prefix = f"{name}.{fps}fps."
            for old in os.listdir(self.cache_dir):
                if old.startswith(prefix) and old != os.path.basename(target):
                    try:
                        os.remove(os.path.join(self.cache_dir, old))
                    except OSError:
                        pass
        return target


def install_static_cache(app, settings: Settings, assets_dir: str, cache_dir: str) -> bool:
    """Troca a rota de assets por uma versao com cache e frame rate opcional.

    Ganho principal: hoje o navegador revalida cada asset a cada partida
    (centenas de idas e vindas ao servidor). Com `Cache-Control` de longa
    duracao a segunda partida em diante nao faz nenhum pedido de asset.
    """
    endpoint = "static_assets_loader"
    if endpoint not in app.view_functions:
        return False

    frame_cache = SwfFrameRateCache(cache_dir)
    max_age = settings.cache_max_age

    def static_assets_loader(path):
        fps = settings.fps
        requested = request.args.get("_fps")
        if requested:
            try:
                fps = int(requested)
            except ValueError:
                fps = settings.fps

        if fps and path.startswith(ROOT_SWF_DIR) and path.lower().endswith(".swf"):
            source = os.path.join(assets_dir, *path.split("/"))
            if os.path.isfile(source):
                try:
                    patched = frame_cache.get(source, fps)
                    response = send_file(
                        patched,
                        mimetype="application/x-shockwave-flash",
                        conditional=True,
                    )
                    response.headers["Cache-Control"] = f"public, max-age={max_age}"
                    response.headers["X-SWBoost-FrameRate"] = str(fps)
                    return response
                except (swf.SwfError, OSError) as exc:
                    # Nunca deixa o jogo cair por causa do boost: se a
                    # reescrita falhar, serve o arquivo original.
                    app.logger.warning("SW Boost: nao consegui ajustar %s (%s)", path, exc)

        response = _send_static(assets_dir, path, max_age)
        response.headers["Cache-Control"] = f"public, max-age={max_age}, immutable"
        return response

    app.view_functions[endpoint] = static_assets_loader
    return True


# --------------------------------------------------------------------------
# config do jogo: serializa uma vez, comprime uma vez
# --------------------------------------------------------------------------


def install_config_cache(app, settings: Settings, get_game_config) -> bool:
    """Guarda o JSON de configuracao (1,6 MB) ja serializado.

    Sem isso, cada carregamento do jogo refaz `make_dynamic()` (que recalcula
    as datas do minigame de dardos com strptime/mktime) e re-serializa o
    dicionario inteiro.
    """
    endpoint = "get_game_config_response"
    if endpoint not in app.view_functions:
        return False

    original = app.view_functions[endpoint]
    state: dict = {"body": None, "gzipped": None, "at": 0.0}
    lock = threading.Lock()

    def _build() -> tuple[bytes, bytes | None]:
        config = get_game_config()
        separators = (",", ":") if settings.compact_config else None
        body = json.dumps(config, separators=separators, ensure_ascii=False).encode("utf-8")
        packed = None
        if settings.gzip_dynamic and len(body) >= settings.gzip_min_size:
            buffer = io.BytesIO()
            with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=6, mtime=0) as out:
                out.write(body)
            packed = buffer.getvalue()
        return body, packed

    def cached_game_config():
        # Mantem os efeitos colaterais do original (validacao dos parametros
        # e o log de qual jogador pediu a config).
        original()

        now = time.monotonic()
        if state["body"] is None or now - state["at"] > settings.config_cache_ttl:
            with lock:
                if state["body"] is None or now - state["at"] > settings.config_cache_ttl:
                    state["body"], state["gzipped"] = _build()
                    state["at"] = now

        accepts_gzip = "gzip" in request.headers.get("Accept-Encoding", "")
        if state["gzipped"] is not None and accepts_gzip:
            response = Response(state["gzipped"], mimetype="application/json")
            response.headers["Content-Encoding"] = "gzip"
        else:
            response = Response(state["body"], mimetype="application/json")

        response.headers["Vary"] = "Accept-Encoding"
        response.headers["Cache-Control"] = "no-store"
        return response

    app.view_functions[endpoint] = cached_game_config
    return True


# --------------------------------------------------------------------------
# compressao das demais respostas dinamicas
# --------------------------------------------------------------------------


def install_gzip(app, settings: Settings) -> None:
    """Comprime respostas dinamicas grandes quando o cliente aceita gzip."""
    if not settings.gzip_dynamic:
        return

    @app.after_request
    def _compress(response: Response) -> Response:
        if response.direct_passthrough:  # arquivos servidos via send_file
            return response
        if response.status_code < 200 or response.status_code >= 300:
            return response
        if response.headers.get("Content-Encoding"):
            return response
        if "gzip" not in request.headers.get("Accept-Encoding", ""):
            return response

        mimetype = (response.mimetype or "").lower()
        if mimetype.startswith(_MIME_ALREADY_COMPRESSED):
            return response

        data = response.get_data()
        if len(data) < settings.gzip_min_size:
            return response

        buffer = io.BytesIO()
        with gzip.GzipFile(fileobj=buffer, mode="wb", compresslevel=6, mtime=0) as out:
            out.write(data)
        response.set_data(buffer.getvalue())
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(response.content_length)
        vary = response.headers.get("Vary")
        response.headers["Vary"] = f"{vary}, Accept-Encoding" if vary else "Accept-Encoding"
        return response


# --------------------------------------------------------------------------
# entrar no jogo com um clique
# --------------------------------------------------------------------------


DEFAULT_GAMEVERSION = "Basesec_1.5.4.swf"


def install_quickplay(app, settings: Settings, sessions_module, state_path: str) -> None:
    """Rota /jogar: entra direto no ultimo save, sem passar pela tela de login."""
    from flask import session as flask_session

    def _remember(userid: str, gameversion: str) -> None:
        try:
            os.makedirs(os.path.dirname(state_path) or ".", exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({"userid": userid, "gameversion": gameversion}, handle)
        except OSError:
            pass

    def _recall() -> tuple[str | None, str]:
        try:
            with open(state_path, encoding="utf-8") as handle:
                data = json.load(handle)
            return data.get("userid"), data.get("gameversion") or DEFAULT_GAMEVERSION
        except (OSError, ValueError):
            return None, DEFAULT_GAMEVERSION

    @app.route("/jogar")
    @app.route("/quickplay")
    def swboost_quickplay():
        sessions_module.load_saves()
        available = sessions_module.all_saves_userid()
        if not available:
            return redirect("/new.html")

        wanted = request.args.get("userid")
        remembered, gameversion = _recall()
        userid = wanted or (remembered if remembered in available else None) or available[0]

        gameversion = request.args.get("gameversion") or gameversion
        flask_session["USERID"] = userid
        flask_session["GAMEVERSION"] = gameversion
        _remember(userid, gameversion)
        return redirect("/play.html")

    # Guarda quem entrou pela tela de login normal, para o /jogar seguinte.
    original_play = app.view_functions.get("play")
    if original_play is not None:

        def play_and_remember(*args, **kwargs):
            result = original_play(*args, **kwargs)
            userid = flask_session.get("USERID")
            if userid:
                _remember(userid, flask_session.get("GAMEVERSION") or DEFAULT_GAMEVERSION)
            return result

        app.view_functions["play"] = play_and_remember


# --------------------------------------------------------------------------
# ajustes na pagina do jogo
# --------------------------------------------------------------------------


_EMBED_RE = re.compile(r"<embed\b[^>]*>", re.IGNORECASE | re.DOTALL)


def _tweak_embed(tag: str, settings: Settings) -> str:
    """Ajusta os atributos do <embed> sem mexer nos flashvars do jogo."""

    def _set(attr: str, value: str, source: str) -> str:
        pattern = re.compile(rf'\b{attr}\s*=\s*(["\']?)[^"\'\s>]*\1', re.IGNORECASE)
        if pattern.search(source):
            return pattern.sub(f'{attr}="{value}"', source, count=1)
        return source[:-1].rstrip() + f' {attr}="{value}">'

    result = tag
    if settings.embed_width:
        result = _set("WIDTH", settings.embed_width, result)
    if settings.embed_height:
        result = _set("HEIGHT", settings.embed_height, result)
    if settings.wmode:
        result = _set("wmode", settings.wmode, result)

    if settings.fps:
        # O frame rate vai na URL do SWF para que cada modo tenha sua propria
        # entrada no cache do navegador.
        def _add_fps(match: re.Match) -> str:
            quote, url = match.group(1), match.group(2)
            if "_fps=" in url:
                return match.group(0)
            joiner = "&" if "?" in url else "?"
            return f'src={quote}{url}{joiner}_fps={settings.fps}{quote}'

        result = re.sub(
            r'src=(["\'])(.*?)\1', _add_fps, result, count=1, flags=re.IGNORECASE | re.DOTALL
        )
    return result


def install_play_page(app, settings: Settings) -> None:
    """Aplica os ajustes opcionais de exibicao na pagina /play.html."""
    if not (settings.embed_width or settings.embed_height or settings.wmode or settings.fps):
        return

    original = app.view_functions.get("play")
    if original is None:
        return

    def play_boosted(*args, **kwargs):
        result = original(*args, **kwargs)
        if not isinstance(result, str):  # redirecionamentos passam direto
            return result
        return _EMBED_RE.sub(lambda m: _tweak_embed(m.group(0), settings), result, count=1)

    app.view_functions["play"] = play_boosted


# --------------------------------------------------------------------------
# diagnostico
# --------------------------------------------------------------------------


def install_health(app, settings: Settings, info: dict) -> None:
    """Endpoint que o lancador usa para saber que o servidor subiu."""

    @app.route("/swboost/health")
    def swboost_health():
        payload = dict(info)
        payload["fps"] = settings.fps or "original (30)"
        payload["cache_max_age"] = settings.cache_max_age
        payload["gzip"] = settings.gzip_dynamic
        return payload, 200

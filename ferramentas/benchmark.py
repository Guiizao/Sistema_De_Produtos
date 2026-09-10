#!/usr/bin/env python3
"""Mede o custo de carregar o Social Wars a partir do servidor.

Simula o que o Flash faz ao abrir uma partida: baixa a configuracao do jogo e
depois uma rajada de sprites. Roda duas vezes para mostrar o efeito do cache
do navegador na segunda partida.

    python ferramentas/benchmark.py                       # servidor turbinado
    python ferramentas/benchmark.py --url http://127.0.0.1:5056  # comparar com outro
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import time
import urllib.error
import urllib.request

CONFIG_PATH = "/dynamic/menvswomen/srvsexwars/get_game_config.php?USERID=1&user_key=1&language=en"
ASSET_PREFIX = "/static/socialwars/"


def fetch(url: str, headers: dict | None = None) -> tuple[int, int, dict, bytes]:
    """Devolve (status, bytes recebidos, cabecalhos, corpo).

    Os cabecalhos vem com as chaves em minusculas: cada servidor HTTP
    normaliza a capitalizacao de um jeito (werkzeug manda `ETag`, waitress
    manda `Etag`) e uma comparacao sensivel a maiusculas erraria o alvo.
    """
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            return response.status, len(body), _lower(response.headers), body
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return exc.code, len(body), _lower(exc.headers), body


def _lower(headers) -> dict:
    return {key.lower(): value for key, value in headers.items()}


def human(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(num) < 1024:
            return f"{num:,.1f} {unit}"
        num /= 1024
    return f"{num:,.1f} TB"


def bench_config(base: str) -> dict:
    url = base + CONFIG_PATH
    start = time.perf_counter()
    status, size, headers, body = fetch(url, {"Accept-Encoding": "gzip"})
    elapsed = time.perf_counter() - start

    encoding = headers.get("content-encoding", "nenhuma")
    if encoding == "gzip":
        body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()

    # Segunda chamada: mostra se o servidor guarda a resposta pronta.
    start = time.perf_counter()
    fetch(url, {"Accept-Encoding": "gzip"})
    second = time.perf_counter() - start

    return {
        "status": status,
        "transferido": size,
        "descompactado": len(body),
        "compressao": encoding,
        "primeira": elapsed,
        "segunda": second,
        "itens": len(json.loads(body.decode("utf-8")).get("items", [])),
    }


def bench_assets(base: str, assets: list) -> dict:
    cold_bytes = cold_time = 0.0
    etags = []

    start = time.perf_counter()
    for path in assets:
        url = base + ASSET_PREFIX + path
        status, size, headers, _ = fetch(url)
        cold_bytes += size
        etags.append((headers.get("etag"), headers.get("cache-control", "")))
    cold_time = time.perf_counter() - start

    # Segunda partida: um navegador SEM Cache-Control revalida cada arquivo.
    warm_bytes = 0
    revalidations = 0
    start = time.perf_counter()
    for index, path in enumerate(assets):
        etag, _cache = etags[index]
        url = base + ASSET_PREFIX + path
        status, size, _headers, _ = fetch(url, {"If-None-Match": etag} if etag else {})
        warm_bytes += size
        if status == 304:
            revalidations += 1
    warm_time = time.perf_counter() - start

    cacheable = sum(1 for _e, cache in etags if "max-age" in cache and "max-age=0" not in cache)

    return {
        "arquivos": len(assets),
        "frio_bytes": cold_bytes,
        "frio_tempo": cold_time,
        "quente_bytes": warm_bytes,
        "quente_tempo": warm_time,
        "revalidacoes_304": revalidations,
        "com_cache_longo": cacheable,
    }


FALLBACK_SPRITES = (
    "sprites/0001_house_1_m.swf",
    "sprites/0002_depot_wood_1_m.swf",
    "sprites/0003_depot_oil_1_m.swf",
    "sprites/0004_depot_steel_1_m.swf",
    "sprites/0005_depot_gold_1_m.swf",
    "sprites/0006_depot_wood_2_m.swf",
    "sprites/0007_depot_oil_2_m.swf",
    "sprites/0008_depot_steel_2_m.swf",
)


def default_assets(count: int, sprite_dir: str | None = None) -> list:
    """Uma amostra do que o jogo baixa ao abrir a vila.

    Usa arquivos distintos sempre que encontra a pasta de sprites: repetir o
    mesmo asset mediria o cache de disco do sistema, nao o servidor.
    """
    for candidate in filter(None, (sprite_dir, "assets/sprites",
                                   os.path.join("socialwarriors", "assets", "sprites"))):
        if os.path.isdir(candidate):
            names = sorted(n for n in os.listdir(candidate) if n.endswith(".swf"))
            if names:
                return [f"sprites/{name}" for name in names[:count]]

    out = []
    while len(out) < count:
        out.extend(FALLBACK_SPRITES)
    return out[:count]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:5055", help="URL base do servidor")
    parser.add_argument("--assets", type=int, default=40, help="quantos assets baixar")
    parser.add_argument("--sprite-dir", help="pasta assets/sprites (para escolher arquivos reais)")
    args = parser.parse_args(argv)
    base = args.url.rstrip("/")

    print(f"\n  Alvo: {base}\n")

    config = bench_config(base)
    print("  CONFIGURACAO DO JOGO")
    print(f"    itens no catalogo ...... {config['itens']}")
    print(f"    compressao ............. {config['compressao']}")
    print(f"    transferido ............ {human(config['transferido'])}"
          f"  (JSON cru: {human(config['descompactado'])})")
    print(f"    1a chamada ............. {config['primeira'] * 1000:,.1f} ms")
    print(f"    2a chamada ............. {config['segunda'] * 1000:,.1f} ms")

    assets = bench_assets(base, default_assets(args.assets, args.sprite_dir))
    print("\n  ASSETS")
    print(f"    arquivos ............... {assets['arquivos']}")
    print(f"    1a partida ............. {human(assets['frio_bytes'])}"
          f" em {assets['frio_tempo'] * 1000:,.0f} ms")
    print(f"    2a partida (revalida) .. {human(assets['quente_bytes'])}"
          f" em {assets['quente_tempo'] * 1000:,.0f} ms"
          f"  ({assets['revalidacoes_304']} respostas 304)")
    print(f"    com cache longo ........ {assets['com_cache_longo']}/{assets['arquivos']}")
    if assets["com_cache_longo"] == assets["arquivos"]:
        print("      -> o navegador nem chega a pedir esses arquivos de novo")
    else:
        print("      -> sem Cache-Control, o navegador pede TODOS de novo a cada partida")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

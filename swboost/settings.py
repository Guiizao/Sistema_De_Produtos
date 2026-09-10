"""Configuracao do SW Boost.

A ordem de precedencia e: padrao < arquivo `swboost.ini` < variaveis de
ambiente `SWBOOST_*` < argumentos de linha de comando.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass, fields
from typing import Any

CONFIG_FILENAME = "swboost.ini"
SECTION = "swboost"

# Um ano. Os assets do jogo sao imutaveis (o pacote nunca muda em disco),
# entao vale a pena deixar o navegador guardar tudo.
ONE_YEAR = 31536000


@dataclass
class Settings:
    # --- servidor ---
    host: str = "127.0.0.1"
    port: int = 5055
    threads: int = 8
    server: str = "auto"  # auto | waitress | flask

    # --- desempenho ---
    cache_max_age: int = ONE_YEAR
    gzip_dynamic: bool = True
    gzip_min_size: int = 4096
    config_cache_ttl: int = 300
    compact_config: bool = True
    quiet: bool = True

    # --- taxa de quadros ---
    # 0 = manter o valor original do SWF (30 fps). 60/120 aceleram o jogo
    # inteiro na mesma proporcao: veja ANALISE_TECNICA.md.
    fps: int = 0

    # --- saves ---
    atomic_saves: bool = True
    compact_saves: bool = False
    save_backups: int = 10
    save_backup_interval: int = 300

    # --- navegador / inicializacao ---
    open_browser: bool = True
    browser: str = "auto"  # auto | none | caminho para o executavel
    quickplay: bool = True

    # --- pagina do jogo ---
    embed_width: str = ""   # vazio = manter o que o jogo ja usa
    embed_height: str = ""
    wmode: str = ""         # vazio = window (o modo mais rapido em plugin)

    @classmethod
    def _coerce(cls, name: str, raw: Any) -> Any:
        target = {f.name: f.type for f in fields(cls)}[name]
        if isinstance(raw, str):
            if target is bool or target == "bool":
                return raw.strip().lower() in ("1", "true", "yes", "on", "sim")
            if target is int or target == "int":
                return int(raw)
        return raw

    def apply(self, values: dict) -> "Settings":
        """Aplica um dicionario de sobrescritas, ignorando valores vazios."""
        known = {f.name for f in fields(self)}
        for key, value in values.items():
            key = key.replace("-", "_").lower()
            if key not in known or value is None:
                continue
            setattr(self, key, self._coerce(key, value))
        return self


def load(config_dir: str, overrides: dict | None = None) -> Settings:
    """Monta as configuracoes a partir do ini, do ambiente e dos overrides."""
    settings = Settings()

    path = os.path.join(config_dir, CONFIG_FILENAME)
    if os.path.isfile(path):
        # strict=False: o arquivo e editado a mao, uma chave repetida nao pode
        # derrubar o lancador (vale a ultima ocorrencia).
        parser = configparser.ConfigParser(strict=False)
        try:
            parser.read(path, encoding="utf-8")
            if parser.has_section(SECTION):
                settings.apply(dict(parser.items(SECTION)))
        except (configparser.Error, ValueError, UnicodeDecodeError) as exc:
            print(f"[!] Ignorando {CONFIG_FILENAME}: {exc}")

    env = {}
    for field in fields(Settings):
        value = os.environ.get("SWBOOST_" + field.name.upper())
        if value is not None:
            env[field.name] = value
    settings.apply(env)

    settings.apply(overrides or {})
    return settings


def write_default(config_dir: str) -> str:
    """Grava um `swboost.ini` comentado. Devolve o caminho do arquivo."""
    path = os.path.join(config_dir, CONFIG_FILENAME)
    defaults = Settings()
    content = f"""# Configuracao do SW Boost para o Social Wars.
# Tudo aqui e opcional: apagar o arquivo volta para os padroes.

[{SECTION}]
# --- servidor ---
host = {defaults.host}
port = {defaults.port}
threads = {defaults.threads}
# auto (usa waitress se estiver instalado), waitress ou flask
server = {defaults.server}

# --- desempenho ---
# Tempo (segundos) que o navegador pode guardar os assets do jogo em cache.
cache_max_age = {defaults.cache_max_age}
# Comprime as respostas dinamicas (config do jogo, dados do jogador).
gzip_dynamic = {defaults.gzip_dynamic}
gzip_min_size = {defaults.gzip_min_size}
# Segundos que a config do jogo (1.6 MB) fica pronta em memoria.
config_cache_ttl = {defaults.config_cache_ttl}
compact_config = {defaults.compact_config}
# Esconde as mensagens repetitivas do console (comandos, assets, saves).
quiet = {defaults.quiet}

# --- taxa de quadros ---
# 0 mantem os 30 fps originais.
# ATENCAO: 60 ou 120 deixam o jogo INTEIRO mais rapido na mesma proporcao,
# porque a logica do Social Wars conta quadros e nao tempo real.
# Leia ANALISE_TECNICA.md antes de mudar.
fps = {defaults.fps}

# --- saves ---
# Grava em arquivo temporario e so entao substitui o save (evita corrupcao).
atomic_saves = {defaults.atomic_saves}
compact_saves = {defaults.compact_saves}
save_backups = {defaults.save_backups}
save_backup_interval = {defaults.save_backup_interval}

# --- inicializacao ---
open_browser = {defaults.open_browser}
# auto, none, ou o caminho completo do navegador com Flash
browser = {defaults.browser}
# Entra direto no ultimo save, pulando a tela de login.
quickplay = {defaults.quickplay}

# --- pagina do jogo ---
# Vazio mantem o que o jogo ja usa hoje.
embed_width =
embed_height =
# Vazio = modo "window" (o mais rapido no plugin). Alternativas: direct, gpu.
wmode =
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path

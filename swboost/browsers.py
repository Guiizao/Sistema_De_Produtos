"""Descoberta e abertura de um navegador capaz de rodar Flash.

Objetivo: tirar do jogador o passo manual de "abra um navegador Flash e
digite http://127.0.0.1:5055". O lancador procura, nesta ordem:

1. um navegador ou projector portatil colocado na pasta do jogo (`browser/`);
2. instalacoes conhecidas de navegadores com Flash;
3. restos de uma instalacao antiga do Flash na propria maquina - inclusive o
   `FlashPlayerApp.exe`, que o instalador do Flash ActiveX deixa no Windows e
   e um projector completo;
4. o navegador padrao do sistema (ultimo recurso - pode nao ter Flash).

O projector e o caminho mais util em maquina sem permissao de administrador:
e um unico executavel, nao instala nada e abre o jogo sem navegador.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass, field

# Versao do PPAPI usada nas instrucoes oficiais do projeto (LINUX.md).
PPAPI_VERSION = "32.0.0.371"
LINUX_PPAPI_PATHS = (
    "/usr/lib/adobe-flashplugin/libpepflashplayer.so",
    "/usr/lib64/adobe-flashplugin/libpepflashplayer.so",
    "/opt/google/chrome/PepperFlash/libpepflashplayer.so",
)

# O instalador do Flash ActiveX deixa um projector completo aqui. Em muita
# maquina corporativa ele ainda existe, e roda sem instalar nada.
WINDOWS_PROJECTOR_PATHS = (
    r"%SystemRoot%\SysWOW64\Macromed\Flash\FlashPlayerApp.exe",
    r"%SystemRoot%\System32\Macromed\Flash\FlashPlayerApp.exe",
    r"%PROGRAMFILES%\Adobe\flashplayer_32_sa.exe",
    r"%PROGRAMFILES(X86)%\Adobe\flashplayer_32_sa.exe",
)

# Nomes que denunciam um projector standalone dentro de `browser/`.
PROJECTOR_HINTS = ("flashplayer", "flashplayerapp", "_sa", "projector")


@dataclass
class Browser:
    name: str
    path: str
    kind: str = "browser"  # browser | chromium-ppapi | projector | system
    extra_args: list = field(default_factory=list)

    def command(self, url: str) -> list:
        return [self.path, *self.extra_args, url]

    def describe(self) -> str:
        return f"{self.name} ({self.path})"


def _expand(paths) -> list:
    out = []
    for raw in paths:
        expanded = os.path.expandvars(os.path.expanduser(raw))
        if "%" not in expanded and os.path.isfile(expanded):
            out.append(expanded)
    return out


def _portable_candidates(game_dir: str) -> list:
    """Navegador ou projector colocado pelo jogador em `<pasta do jogo>/browser/`."""
    found = []
    for folder in (os.path.join(game_dir, "browser"), os.path.join(game_dir, "navegador")):
        if not os.path.isdir(folder):
            continue
        for root, _dirs, files in os.walk(folder):
            for name in files:
                lowered = name.lower()
                if not (lowered.endswith(".exe") or (os.name != "nt" and "." not in name)):
                    continue
                if not any(key in lowered for key in ("flash", "basilisk", "palemoon",
                                                      "waterfox", "chrome", "firefox")):
                    continue
                kind = "projector" if any(h in lowered for h in PROJECTOR_HINTS) else "browser"
                found.append(Browser(name, os.path.join(root, name), kind=kind))
            if len(found) > 4:
                break
    # Projector primeiro: dispensa instalacao e e o caminho sem administrador.
    found.sort(key=lambda b: 0 if b.kind == "projector" else 1)
    return found


def _windows_candidates() -> list:
    found = []

    flash_browsers = [
        (r"%LOCALAPPDATA%\Programs\FlashBrowser\FlashBrowser.exe", "FlashBrowser"),
        (r"%PROGRAMFILES%\FlashBrowser\FlashBrowser.exe", "FlashBrowser"),
        (r"%PROGRAMFILES(X86)%\FlashBrowser\FlashBrowser.exe", "FlashBrowser"),
        (r"%PROGRAMFILES%\Basilisk\basilisk.exe", "Basilisk"),
        (r"%PROGRAMFILES(X86)%\Basilisk\basilisk.exe", "Basilisk"),
        (r"%PROGRAMFILES%\Pale Moon\palemoon.exe", "Pale Moon"),
        (r"%PROGRAMFILES(X86)%\Pale Moon\palemoon.exe", "Pale Moon"),
        (r"%PROGRAMFILES%\Waterfox Classic\waterfox.exe", "Waterfox Classic"),
    ]
    for raw, name in flash_browsers:
        for path in _expand([raw]):
            found.append(Browser(name, path))

    for raw in WINDOWS_PROJECTOR_PATHS:
        for path in _expand([raw]):
            found.append(Browser("Flash Player standalone", path, kind="projector"))

    return found


def _linux_candidates() -> list:
    found = []

    for exe, name in (("basilisk", "Basilisk"), ("palemoon", "Pale Moon"),
                      ("waterfox", "Waterfox")):
        path = shutil.which(exe)
        if path:
            found.append(Browser(name, path))

    ppapi = next((p for p in LINUX_PPAPI_PATHS if os.path.isfile(p)), None)
    if ppapi:
        for exe, name in (("chromium", "Chromium"), ("chromium-browser", "Chromium"),
                          ("google-chrome", "Google Chrome")):
            path = shutil.which(exe)
            if path:
                found.append(
                    Browser(
                        f"{name} + PPAPI Flash",
                        path,
                        kind="chromium-ppapi",
                        extra_args=[
                            f"--ppapi-flash-path={ppapi}",
                            f"--ppapi-flash-version={PPAPI_VERSION}",
                        ],
                    )
                )
                break

    for exe in ("flashplayer", "flashplayerdebugger", "flashplayer_32_sa"):
        path = shutil.which(exe)
        if path:
            found.append(Browser("Flash Player standalone", path, kind="projector"))
            break

    return found


def discover(game_dir: str = ".") -> list:
    """Lista os navegadores com Flash encontrados na maquina."""
    candidates = _portable_candidates(game_dir)
    if platform.system() == "Windows":
        candidates += _windows_candidates()
    else:
        candidates += _linux_candidates()

    seen, unique = set(), []
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(candidate.path))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def resolve(preference: str, game_dir: str = ".") -> Browser | None:
    """Escolhe o navegador a usar. `preference` pode ser auto, none ou um caminho."""
    preference = (preference or "auto").strip()
    if preference.lower() in ("none", "nao", "nenhum", ""):
        return None
    if preference.lower() != "auto":
        path = os.path.expandvars(os.path.expanduser(preference))
        if os.path.isfile(path):
            return Browser(os.path.basename(path), path)
        return None

    found = discover(game_dir)
    return found[0] if found else None


def open_url(url: str, browser: Browser | None) -> str:
    """Abre a URL. Devolve uma descricao do que foi usado."""
    if browser is None:
        webbrowser.open(url)
        return "navegador padrao do sistema (pode nao ter suporte a Flash)"

    try:
        subprocess.Popen(
            browser.command(url),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return browser.describe()
    except OSError as exc:
        webbrowser.open(url)
        return f"navegador padrao do sistema (falha ao abrir {browser.name}: {exc})"

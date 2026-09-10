"""Gravacao segura dos saves do Social Wars.

O `sessions.save_session()` original abre o arquivo do save em modo "w" (o que
trunca o arquivo na hora) e so depois escreve o JSON. Se o processo morrer no
meio - fechar a janela, queda de energia, matar o servidor - o save fica
truncado. Na proxima inicializacao o `load_saves()` apenas imprime
"Corrupted JSON" e segue adiante: a vila desaparece da tela de login.

Aqui a gravacao passa a ser atomica (escreve em um temporario e so entao
substitui o arquivo) e passa a manter copias de seguranca rotativas.

Os backups NAO ficam dentro de `saves/`. O `load_saves()` original percorre
`os.listdir(SAVES_DIR)` e chama `json.load(open(...))` em cada entrada, sem
verificar se e um arquivo - uma subpasta ali dentro levanta IsADirectoryError
e derruba o servidor na inicializacao (o except so cobre JSONDecodeError).
Por isso as copias vao para uma pasta separada, fora do caminho do jogo.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time

# Fora de `saves/` de proposito - veja a nota no topo do modulo.
BACKUP_DIRNAME = "save_backups"


def _rotate_backup(backup_dir: str, userid: str, path: str, keep: int, interval: int) -> None:
    """Copia o save atual para a pasta de backups, respeitando o intervalo."""
    prefix = f"{userid}.save."

    try:
        os.makedirs(backup_dir, exist_ok=True)
        existing = sorted(
            entry for entry in os.listdir(backup_dir) if entry.startswith(prefix)
        )
    except OSError:
        return

    now = time.time()
    if existing:
        newest = os.path.join(backup_dir, existing[-1])
        try:
            if now - os.path.getmtime(newest) < interval:
                return  # ainda dentro da janela: nao precisa de copia nova
        except OSError:
            pass

    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    try:
        shutil.copy2(path, os.path.join(backup_dir, f"{prefix}{stamp}.json"))
    except OSError:
        return

    try:
        existing = sorted(
            entry for entry in os.listdir(backup_dir) if entry.startswith(prefix)
        )
        for stale in existing[:-keep] if keep > 0 else existing:
            os.remove(os.path.join(backup_dir, stale))
    except OSError:
        pass


def backup_dir_for(saves_dir: str) -> str:
    """Pasta de backups: irma de `saves/`, nunca dentro dela."""
    return os.path.join(os.path.dirname(os.path.abspath(saves_dir)), BACKUP_DIRNAME)


def install(sessions_module, saves_dir: str, settings) -> bool:
    """Substitui `save_session` por uma versao atomica, com backups.

    O `command.py` faz `from sessions import save_session`, ou seja, guarda a
    propria referencia para a funcao. Por isso a troca precisa acontecer em
    todos os modulos que ja importaram a funcao original, e nao so em
    `sessions`.
    """
    if not settings.atomic_saves:
        return False

    original = getattr(sessions_module, "save_session", None)
    if original is None or getattr(original, "_swboost", False):
        return False

    indent = None if settings.compact_saves else 4
    keep = settings.save_backups
    interval = settings.save_backup_interval
    backup_dir = backup_dir_for(saves_dir)

    def save_session(USERID: str) -> None:
        village = sessions_module.session(USERID)
        if village is None:
            return original(USERID)

        filename = f"{USERID}.save.json"
        path = os.path.join(saves_dir, filename)
        tmp = path + ".swboost-tmp"

        os.makedirs(saves_dir, exist_ok=True)
        payload = json.dumps(village, indent=indent, ensure_ascii=False)

        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        if keep > 0 and os.path.isfile(path):
            _rotate_backup(backup_dir, USERID, path, keep, interval)

        os.replace(tmp, path)  # atomico no Windows e no Linux

    save_session._swboost = True  # type: ignore[attr-defined]
    save_session.__doc__ = original.__doc__

    setattr(sessions_module, "save_session", save_session)
    for module in list(sys.modules.values()):
        if module is None or module is sessions_module:
            continue
        try:
            if getattr(module, "save_session", None) is original:
                setattr(module, "save_session", save_session)
        except Exception:  # modulos exoticos podem explodir no getattr
            continue
    return True


def restore_latest_backup(saves_dir: str, userid: str) -> str | None:
    """Traz de volta o backup mais recente de um save. Devolve o caminho usado."""
    backup_dir = backup_dir_for(saves_dir)
    prefix = f"{userid}.save."
    if not os.path.isdir(backup_dir):
        return None

    candidates = sorted(
        entry for entry in os.listdir(backup_dir) if entry.startswith(prefix)
    )
    if not candidates:
        return None

    newest = os.path.join(backup_dir, candidates[-1])
    shutil.copy2(newest, os.path.join(saves_dir, f"{userid}.save.json"))
    return newest


def unsafe_saves_entries(saves_dir: str) -> list:
    """Entradas em `saves/` que fariam o load_saves() original explodir.

    O jogo tenta abrir tudo o que estiver na pasta como JSON. Uma subpasta
    levanta IsADirectoryError durante o import do servidor - antes de qualquer
    codigo do boost rodar - entao o melhor que da para fazer e avisar cedo.
    """
    if not os.path.isdir(saves_dir):
        return []
    problemas = []
    for entry in sorted(os.listdir(saves_dir)):
        full = os.path.join(saves_dir, entry)
        if os.path.isdir(full):
            problemas.append(entry + os.sep)
    return problemas

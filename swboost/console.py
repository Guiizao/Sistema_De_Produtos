"""Filtro de saida do console.

O servidor do Social Wars imprime uma linha por comando do jogo, por asset e
por gravacao de save. Em uma partida normal isso vira milhares de linhas. No
Windows, escrever no console e uma chamada de sistema sincrona e cara: em
partidas grandes o proprio log passa a ser um gargalo perceptivel.

O filtro descarta apenas as linhas repetitivas conhecidas e deixa passar tudo
o mais (erros, avisos, o log de inicializacao). `--verbose` desliga o filtro.
"""

from __future__ import annotations

import sys
import threading

NOISY_PREFIXES = (
    " [+] COMMAND: ",
    "[CONFIG] USERID",
    "[STATUS] USERID",
    "[PLAYER INFO] USERID",
    " * Saving village at",
)


class FilteredStream:
    """Envolve um stream de texto e descarta linhas ruidosas.

    O buffer e por thread: com o servidor multi-thread, duas requisicoes
    simultaneas nao misturam pedacos de linha uma da outra.
    """

    def __init__(self, stream, prefixes=NOISY_PREFIXES) -> None:
        self._stream = stream
        self._prefixes = tuple(prefixes)
        self._local = threading.local()
        self._lock = threading.Lock()
        self.dropped = 0

    def _buffer(self) -> list:
        if not hasattr(self._local, "parts"):
            self._local.parts = []
        return self._local.parts

    def _emit(self, line: str) -> None:
        if line.startswith(self._prefixes):
            with self._lock:
                self.dropped += 1
            return
        self._stream.write(line)

    def write(self, text: str) -> int:
        if not text:
            return 0
        parts = self._buffer()
        parts.append(text)

        joined = "".join(parts)
        if "\n" not in joined:
            return len(text)

        *lines, remainder = joined.split("\n")
        for line in lines:
            self._emit(line + "\n")
        parts.clear()
        if remainder:
            parts.append(remainder)
        return len(text)

    def flush(self) -> None:
        parts = self._buffer()
        if parts:
            self._emit("".join(parts))
            parts.clear()
        self._stream.flush()

    def isatty(self) -> bool:
        return getattr(self._stream, "isatty", lambda: False)()

    def fileno(self) -> int:
        return self._stream.fileno()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def install() -> FilteredStream:
    """Liga o filtro no stdout do processo. Devolve o stream instalado."""
    if isinstance(sys.stdout, FilteredStream):
        return sys.stdout
    stream = FilteredStream(sys.stdout)
    sys.stdout = stream
    return stream


def uninstall() -> None:
    if isinstance(sys.stdout, FilteredStream):
        sys.stdout.flush()
        sys.stdout = sys.stdout._stream

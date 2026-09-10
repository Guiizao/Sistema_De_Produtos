"""Leitura e reescrita do cabecalho de arquivos SWF.

O cabecalho de um SWF guarda o frame rate do filme. Para o SWF que fica na
raiz (o que o navegador carrega no <embed>), esse valor vira o `stage.frameRate`
do Flash Player e controla TODO o jogo: renderizacao, timeline de animacao e
o loop de logica.

Formato (SWF File Format Specification v19, secao "The SWF header"):

    bytes 0..2   assinatura: "FWS" (sem compressao), "CWS" (zlib), "ZWS" (LZMA)
    byte  3      versao do SWF
    bytes 4..7   UI32 little-endian, tamanho total do arquivo DESCOMPACTADO
    ---- a partir daqui o conteudo pode estar compactado ----
    RECT         frameSize (tamanho do palco, em twips)
    UI16         frameRate em ponto fixo 8.8 (byte baixo = fracao)
    UI16         frameCount

Como so mexemos em 2 bytes dentro do corpo, o tamanho descompactado nao muda.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

TWIPS_PER_PIXEL = 20

# O Flash Player limita stage.frameRate a 120 fps.
MAX_FRAME_RATE = 120.0
MIN_FRAME_RATE = 0.01


class SwfError(Exception):
    """Erro ao interpretar ou reescrever um SWF."""


@dataclass(frozen=True)
class SwfHeader:
    signature: str
    version: int
    file_length: int
    frame_rate: float
    frame_count: int
    width: float
    height: float

    def describe(self) -> str:
        comp = {"FWS": "sem compressao", "CWS": "zlib", "ZWS": "LZMA"}
        return (
            f"SWF v{self.version} ({comp.get(self.signature, self.signature)}), "
            f"palco {self.width:.0f}x{self.height:.0f}, "
            f"{self.frame_rate:g} fps, {self.frame_count} frame(s)"
        )


def _split(data: bytes) -> tuple[str, int, int, bytes]:
    """Devolve (assinatura, versao, file_length declarado, corpo descompactado)."""
    if len(data) < 9:
        raise SwfError("arquivo pequeno demais para ser um SWF")

    signature = data[0:3].decode("latin-1")
    if signature not in ("FWS", "CWS", "ZWS"):
        raise SwfError(f"assinatura desconhecida: {signature!r} (nao e um SWF)")

    version = data[3]
    file_length = struct.unpack("<I", data[4:8])[0]

    if signature == "FWS":
        body = data[8:]
    elif signature == "CWS":
        try:
            body = zlib.decompress(data[8:])
        except zlib.error as exc:
            raise SwfError(f"falha ao descompactar SWF zlib: {exc}") from exc
    else:  # ZWS
        raise SwfError(
            "SWF comprimido com LZMA (ZWS) ainda nao e suportado para reescrita"
        )

    return signature, version, file_length, body


def _rect_length(body: bytes) -> int:
    """Tamanho em bytes do RECT que abre o corpo do SWF."""
    if not body:
        raise SwfError("corpo do SWF vazio")
    nbits = body[0] >> 3
    total_bits = 5 + 4 * nbits
    return (total_bits + 7) // 8


def _rect_dimensions(body: bytes, rect_len: int) -> tuple[float, float]:
    """Largura e altura do palco, em pixels."""
    nbits = body[0] >> 3
    if nbits == 0:
        return 0.0, 0.0
    bits = "".join(f"{b:08b}" for b in body[:rect_len])
    pos = 5
    values = []
    for _ in range(4):
        chunk = bits[pos : pos + nbits]
        values.append(int(chunk, 2) if chunk else 0)
        pos += nbits
    xmin, xmax, ymin, ymax = values
    return (xmax - xmin) / TWIPS_PER_PIXEL, (ymax - ymin) / TWIPS_PER_PIXEL


def read_header(data: bytes) -> SwfHeader:
    """Le o cabecalho de um SWF ja carregado em memoria."""
    signature, version, file_length, body = _split(data)
    rect_len = _rect_length(body)
    if len(body) < rect_len + 4:
        raise SwfError("corpo do SWF truncado antes do frame rate")

    raw_rate = struct.unpack("<H", body[rect_len : rect_len + 2])[0]
    frame_count = struct.unpack("<H", body[rect_len + 2 : rect_len + 4])[0]
    width, height = _rect_dimensions(body, rect_len)

    return SwfHeader(
        signature=signature,
        version=version,
        file_length=file_length,
        frame_rate=raw_rate / 256.0,
        frame_count=frame_count,
        width=width,
        height=height,
    )


def read_header_file(path: str) -> SwfHeader:
    """Le o cabecalho direto de um arquivo em disco."""
    with open(path, "rb") as handle:
        # 4 KiB e suficiente para o cabecalho, mas o zlib precisa do stream
        # inteiro para descompactar de forma confiavel em arquivos pequenos.
        data = handle.read()
    return read_header(data)


def set_frame_rate(data: bytes, fps: float, compress_level: int = 6) -> bytes:
    """Devolve uma copia do SWF com outro frame rate.

    A compressao original e preservada: um CWS continua CWS. O campo
    `file_length` e recalculado a partir do corpo real, o que tambem conserta
    arquivos cujo cabecalho estivesse dessincronizado.
    """
    if not (MIN_FRAME_RATE <= fps <= MAX_FRAME_RATE):
        raise SwfError(
            f"frame rate {fps} fora do intervalo suportado pelo Flash Player "
            f"({MIN_FRAME_RATE}-{MAX_FRAME_RATE} fps)"
        )

    signature, version, _file_length, body = _split(data)
    rect_len = _rect_length(body)
    if len(body) < rect_len + 4:
        raise SwfError("corpo do SWF truncado antes do frame rate")

    raw_rate = int(round(fps * 256))
    raw_rate = max(1, min(raw_rate, 0xFFFF))

    patched = bytearray(body)
    patched[rect_len : rect_len + 2] = struct.pack("<H", raw_rate)
    body = bytes(patched)

    header = bytearray(data[0:8])
    header[4:8] = struct.pack("<I", 8 + len(body))

    if signature == "FWS":
        return bytes(header) + body
    return bytes(header) + zlib.compress(body, compress_level)


def set_frame_rate_file(path: str, fps: float, dest: str | None = None) -> SwfHeader:
    """Reescreve o frame rate de um SWF em disco e devolve o cabecalho novo."""
    with open(path, "rb") as handle:
        data = handle.read()
    patched = set_frame_rate(data, fps)
    with open(dest or path, "wb") as handle:
        handle.write(patched)
    return read_header(patched)

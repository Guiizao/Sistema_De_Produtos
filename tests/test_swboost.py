"""Testes do SW Boost.

Rode com:  python -m unittest discover -s tests -v

Nenhum teste precisa dos arquivos do jogo: os SWF usados sao construidos na
hora e o modulo de saves e exercitado contra um `sessions` de mentira.
"""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import types
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swboost import console, saves, swf, web  # noqa: E402
from swboost.settings import Settings, load, write_default  # noqa: E402


def _carregar_ferramenta(nome: str):
    """Importa um script de `ferramentas/` (que nao e um pacote) pelo caminho."""
    import importlib.util

    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ferramentas", nome
    )
    spec = importlib.util.spec_from_file_location(nome[:-3], caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


traducao = _carregar_ferramenta("gerar_mod_traducao.py")


# --------------------------------------------------------------------------
# auxiliares
# --------------------------------------------------------------------------


def _rect(width: float, height: float) -> bytes:
    """Codifica um RECT de SWF (0,0)-(width,height) em twips."""
    xmax, ymax = int(width * 20), int(height * 20)
    nbits = max(xmax.bit_length(), ymax.bit_length(), 1)
    bits = f"{nbits:05b}" + "".join(f"{value:0{nbits}b}" for value in (0, xmax, 0, ymax))
    bits += "0" * (-len(bits) % 8)
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def make_swf(fps: float = 30.0, width: float = 760, height: float = 600,
             compressed: bool = True, frames: int = 1) -> bytes:
    body = (
        _rect(width, height)
        + struct.pack("<H", int(round(fps * 256)))
        + struct.pack("<H", frames)
        + b"\x00\x00"  # tag End
    )
    signature = b"CWS" if compressed else b"FWS"
    header = signature + bytes([10]) + struct.pack("<I", 8 + len(body))
    return header + (zlib.compress(body) if compressed else body)


# --------------------------------------------------------------------------
# swboost.swf
# --------------------------------------------------------------------------


class TestSwfHeader(unittest.TestCase):
    def test_le_cabecalho_compactado(self):
        header = swf.read_header(make_swf(fps=30, width=760, height=600))
        self.assertEqual(header.signature, "CWS")
        self.assertEqual(header.version, 10)
        self.assertAlmostEqual(header.frame_rate, 30.0)
        self.assertEqual(header.frame_count, 1)
        self.assertAlmostEqual(header.width, 760, places=1)
        self.assertAlmostEqual(header.height, 600, places=1)

    def test_le_cabecalho_sem_compressao(self):
        header = swf.read_header(make_swf(fps=24, compressed=False))
        self.assertEqual(header.signature, "FWS")
        self.assertAlmostEqual(header.frame_rate, 24.0)

    def test_troca_taxa_de_quadros(self):
        for target in (60, 120, 25.5):
            patched = swf.set_frame_rate(make_swf(fps=30), target)
            self.assertAlmostEqual(swf.read_header(patched).frame_rate, target, places=2)

    def test_preserva_compressao_e_palco(self):
        original = make_swf(fps=30, width=1400, height=600)
        patched = swf.set_frame_rate(original, 60)
        header = swf.read_header(patched)
        self.assertEqual(header.signature, "CWS")
        self.assertAlmostEqual(header.width, 1400, places=1)
        self.assertAlmostEqual(header.height, 600, places=1)
        self.assertEqual(header.frame_count, 1)

    def test_file_length_bate_com_o_conteudo(self):
        patched = swf.set_frame_rate(make_swf(fps=30, compressed=False), 60)
        self.assertEqual(swf.read_header(patched).file_length, len(patched))

    def test_ida_e_volta_preserva_o_corpo(self):
        original = make_swf(fps=30, compressed=False)
        again = swf.set_frame_rate(swf.set_frame_rate(original, 120), 30)
        self.assertEqual(again, original)

    def test_recusa_arquivo_que_nao_e_swf(self):
        with self.assertRaises(swf.SwfError):
            swf.read_header(b"PK\x03\x04" + b"\x00" * 40)

    def test_recusa_arquivo_curto(self):
        with self.assertRaises(swf.SwfError):
            swf.read_header(b"FWS")

    def test_recusa_taxa_fora_do_limite_do_flash(self):
        data = make_swf()
        for invalid in (0, 121, -5, 1000):
            with self.assertRaises(swf.SwfError):
                swf.set_frame_rate(data, invalid)

    def test_grava_em_disco_e_le_de_volta(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "teste.swf")
            with open(path, "wb") as handle:
                handle.write(make_swf(fps=30))
            header = swf.set_frame_rate_file(path, 60)
            self.assertAlmostEqual(header.frame_rate, 60.0)
            self.assertAlmostEqual(swf.read_header_file(path).frame_rate, 60.0)


# --------------------------------------------------------------------------
# swboost.web - cache de SWF e ajuste do <embed>
# --------------------------------------------------------------------------


class TestSwfFrameRateCache(unittest.TestCase):
    def test_gera_e_reaproveita_o_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "SWLoader.swf")
            with open(source, "wb") as handle:
                handle.write(make_swf(fps=30))

            cache = web.SwfFrameRateCache(os.path.join(tmp, "cache"))
            first = cache.get(source, 60)
            self.assertAlmostEqual(swf.read_header_file(first).frame_rate, 60.0)

            # A segunda chamada devolve o mesmo arquivo, sem regravar.
            before = os.path.getmtime(first)
            self.assertEqual(cache.get(source, 60), first)
            self.assertEqual(os.path.getmtime(first), before)

    def test_refaz_o_cache_quando_o_original_muda(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "SWLoader.swf")
            with open(source, "wb") as handle:
                handle.write(make_swf(fps=30, width=760))
            cache = web.SwfFrameRateCache(os.path.join(tmp, "cache"))
            first = cache.get(source, 60)

            with open(source, "wb") as handle:
                handle.write(make_swf(fps=30, width=1400))
            os.utime(source, (0, 0))

            second = cache.get(source, 60)
            self.assertNotEqual(first, second)
            self.assertAlmostEqual(swf.read_header_file(second).width, 1400, places=1)


class TestEmbedTweak(unittest.TestCase):
    TAG = (
        '<embed id="swf" src="http://127.0.0.1:5055/static/socialwars/flash/'
        'SWLoader.swf?swftoload=/static/socialwars/flash/Basesec_1.5.4.swf" '
        'allowFullScreen="true" quality=high WIDTH="760" HEIGHT="600" '
        "flashvars='spdebug=notnull&brk=0&language=en&brk=0'>"
    )

    def test_acrescenta_fps_na_url(self):
        out = web._tweak_embed(self.TAG, Settings(fps=60))
        self.assertIn("_fps=60", out)
        self.assertIn("swftoload=", out)
        self.assertIn("spdebug=notnull", out)

    def test_nao_duplica_o_fps(self):
        once = web._tweak_embed(self.TAG, Settings(fps=60))
        twice = web._tweak_embed(once, Settings(fps=60))
        self.assertEqual(twice.count("_fps="), 1)

    def test_troca_tamanho_e_wmode(self):
        out = web._tweak_embed(self.TAG, Settings(embed_width="1400", wmode="direct"))
        self.assertIn('WIDTH="1400"', out)
        self.assertIn('wmode="direct"', out)
        self.assertNotIn('WIDTH="760"', out)

    def test_sem_configuracao_nao_mexe_no_tag(self):
        self.assertEqual(web._tweak_embed(self.TAG, Settings()), self.TAG)


# --------------------------------------------------------------------------
# swboost.settings
# --------------------------------------------------------------------------


class TestSettings(unittest.TestCase):
    def test_padroes_conservadores(self):
        defaults = Settings()
        self.assertEqual(defaults.fps, 0, "o padrao precisa manter os 30 fps originais")
        self.assertEqual(defaults.port, 5055)
        self.assertTrue(defaults.atomic_saves)

    def test_le_do_arquivo_ini(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "swboost.ini"), "w", encoding="utf-8") as handle:
                handle.write("[swboost]\nport = 6000\nfps = 60\nquiet = false\n")
            cfg = load(tmp)
            self.assertEqual(cfg.port, 6000)
            self.assertEqual(cfg.fps, 60)
            self.assertFalse(cfg.quiet)

    def test_o_ini_padrao_e_lido_sem_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_default(tmp)
            self.assertEqual(load(tmp).port, Settings().port)

    def test_ini_quebrado_nao_derruba_o_lancador(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "swboost.ini"), "w", encoding="utf-8") as handle:
                handle.write("[swboost]\nport = 6000\nport = 6001\nlixo sem igual\n")
            self.assertIsInstance(load(tmp), Settings)

    def test_ambiente_ganha_do_arquivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_default(tmp)
            os.environ["SWBOOST_PORT"] = "7000"
            try:
                self.assertEqual(load(tmp).port, 7000)
            finally:
                del os.environ["SWBOOST_PORT"]

    def test_argumentos_ganham_de_tudo(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_default(tmp)
            os.environ["SWBOOST_PORT"] = "7000"
            try:
                self.assertEqual(load(tmp, {"port": 8000}).port, 8000)
            finally:
                del os.environ["SWBOOST_PORT"]

    def test_aceita_sim_como_verdadeiro(self):
        self.assertTrue(Settings().apply({"quiet": "sim"}).quiet)
        self.assertFalse(Settings().apply({"quiet": "nao"}).quiet)


# --------------------------------------------------------------------------
# swboost.console
# --------------------------------------------------------------------------


class _Sink:
    def __init__(self):
        self.text = ""

    def write(self, value):
        self.text += value
        return len(value)

    def flush(self):
        pass


class TestConsoleFilter(unittest.TestCase):
    def test_descarta_linhas_repetitivas(self):
        sink = _Sink()
        stream = console.FilteredStream(sink)
        stream.write(" [+] COMMAND: buy(1) -> Add House\n")
        stream.write("[CONFIG] USERID 42.\n")
        self.assertEqual(sink.text, "")
        self.assertEqual(stream.dropped, 2)

    def test_deixa_passar_o_resto(self):
        sink = _Sink()
        stream = console.FilteredStream(sink)
        stream.write(" [+] Loading server...\n")
        stream.write("[VISIT] USERID 1 visiting user: 2.\n")
        self.assertIn("Loading server", sink.text)
        self.assertIn("[VISIT]", sink.text)

    def test_junta_escritas_parciais_antes_de_decidir(self):
        # O jogo imprime em pedacos: print(..., end='') e so depois o resto.
        sink = _Sink()
        stream = console.FilteredStream(sink)
        stream.write(" * Saving village at abc.save.json... ")
        self.assertEqual(sink.text, "")  # ainda nao sabe se a linha e ruidosa
        stream.write("Done.\n")
        self.assertEqual(sink.text, "")  # linha completa: era ruidosa

    def test_flush_esvazia_linha_incompleta(self):
        sink = _Sink()
        stream = console.FilteredStream(sink)
        stream.write("erro sem quebra de linha")
        stream.flush()
        self.assertEqual(sink.text, "erro sem quebra de linha")


# --------------------------------------------------------------------------
# swboost.saves
# --------------------------------------------------------------------------


def _fake_sessions(store: dict) -> types.ModuleType:
    module = types.ModuleType("fake_sessions")
    module.session = lambda userid: store.get(userid)

    def save_session(userid):  # a versao original, nao-atomica
        module.calls.append(userid)

    module.calls = []
    module.save_session = save_session
    return module


class TestAtomicSaves(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saves_dir = os.path.join(self.tmp.name, "saves")
        os.makedirs(self.saves_dir)
        self.village = {"playerInfo": {"pid": "u1", "name": "Vila"}, "maps": [], "privateState": {}}
        self.sessions = _fake_sessions({"u1": self.village})

    def tearDown(self):
        self.tmp.cleanup()

    def test_grava_json_valido(self):
        saves.install(self.sessions, self.saves_dir, Settings())
        self.sessions.save_session("u1")
        path = os.path.join(self.saves_dir, "u1.save.json")
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), self.village)

    def test_nao_deixa_arquivo_temporario_para_tras(self):
        saves.install(self.sessions, self.saves_dir, Settings())
        self.sessions.save_session("u1")
        leftovers = [n for n in os.listdir(self.saves_dir) if n.endswith("-tmp")]
        self.assertEqual(leftovers, [])

    def test_cria_backup_rotativo(self):
        cfg = Settings(save_backups=3, save_backup_interval=0)
        saves.install(self.sessions, self.saves_dir, cfg)
        for index in range(5):
            self.village["playerInfo"]["name"] = f"Vila {index}"
            self.sessions.save_session("u1")

        backup_dir = saves.backup_dir_for(self.saves_dir)
        backups = sorted(os.listdir(backup_dir))
        self.assertLessEqual(len(backups), 3, "a rotacao precisa limitar os backups")
        self.assertTrue(backups, "deveria existir pelo menos um backup")

    def test_respeita_o_intervalo_entre_backups(self):
        cfg = Settings(save_backups=10, save_backup_interval=3600)
        saves.install(self.sessions, self.saves_dir, cfg)
        for _ in range(4):
            self.sessions.save_session("u1")
        backup_dir = saves.backup_dir_for(self.saves_dir)
        self.assertEqual(len(os.listdir(backup_dir)), 1, "so um backup dentro da janela")

    def test_restaura_backup_mais_recente(self):
        cfg = Settings(save_backups=5, save_backup_interval=0)
        saves.install(self.sessions, self.saves_dir, cfg)
        self.sessions.save_session("u1")
        self.village["playerInfo"]["name"] = "Depois"
        self.sessions.save_session("u1")

        path = os.path.join(self.saves_dir, "u1.save.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("{corrompido")

        self.assertIsNotNone(saves.restore_latest_backup(self.saves_dir, "u1"))
        with open(path, encoding="utf-8") as handle:
            json.load(handle)  # volta a ser JSON valido

    def test_substitui_a_funcao_em_outros_modulos(self):
        # command.py faz `from sessions import save_session`, guardando a
        # propria referencia. A troca precisa alcancar esse modulo tambem.
        consumer = types.ModuleType("fake_command")
        consumer.save_session = self.sessions.save_session
        sys.modules["fake_command"] = consumer
        try:
            saves.install(self.sessions, self.saves_dir, Settings())
            self.assertIs(consumer.save_session, self.sessions.save_session)
            consumer.save_session("u1")
            self.assertTrue(os.path.isfile(os.path.join(self.saves_dir, "u1.save.json")))
        finally:
            del sys.modules["fake_command"]

    def test_backups_ficam_fora_da_pasta_saves(self):
        # Uma subpasta em saves/ faz o load_saves() do jogo levantar
        # IsADirectoryError e derrubar o servidor na inicializacao.
        cfg = Settings(save_backups=3, save_backup_interval=0)
        saves.install(self.sessions, self.saves_dir, cfg)
        self.sessions.save_session("u1")
        self.sessions.save_session("u1")

        entradas = os.listdir(self.saves_dir)
        self.assertTrue(all(os.path.isfile(os.path.join(self.saves_dir, e)) for e in entradas),
                        f"saves/ so pode conter arquivos, mas tem: {entradas}")
        self.assertTrue(os.path.isdir(saves.backup_dir_for(self.saves_dir)))

    def test_detecta_pasta_intrusa_em_saves(self):
        self.assertEqual(saves.unsafe_saves_entries(self.saves_dir), [])
        os.makedirs(os.path.join(self.saves_dir, "antigos"))
        self.assertEqual(saves.unsafe_saves_entries(self.saves_dir), ["antigos" + os.sep])

    def test_desligado_mantem_a_funcao_original(self):
        saves.install(self.sessions, self.saves_dir, Settings(atomic_saves=False))
        self.sessions.save_session("u1")
        self.assertEqual(self.sessions.calls, ["u1"])


# --------------------------------------------------------------------------
# ferramentas/gerar_mod_traducao.py
# --------------------------------------------------------------------------


class TestGeradorTraducao(unittest.TestCase):
    def test_expressao_composta_ganha_da_palavra_solta(self):
        # "Wood Factory" precisa virar "Fabrica de Madeira", nao "Madeira Fabrica".
        self.assertEqual(traducao.traduzir("Wood Factory I"), "Fábrica de Madeira I")
        self.assertEqual(traducao.traduzir("Steel Factory II"), "Fábrica de Aço II")

    def test_traduz_palavra_solta(self):
        self.assertEqual(traducao.traduzir("House I"), "Casa I")
        self.assertEqual(traducao.traduzir("Wall III"), "Muro III")

    def test_respeita_limite_de_palavra(self):
        # "Housekeeper" nao pode virar "Casakeeper".
        self.assertEqual(traducao.traduzir("Housekeeper"), "Housekeeper")

    def test_deixa_intacto_o_que_nao_conhece(self):
        self.assertEqual(traducao.traduzir("Vortex Drone"), "Vortex Drone")

    def test_gera_caminhos_validos(self):
        config = {
            "items": [{"name": "House I"}, {"name": "Wall II"}],
            "goals": [{"title": "Build a House", "hint": "", "description": "Do it"}],
        }
        operacoes, mantidos, novos = traducao.gerar(config, {})
        caminhos = [operacao["path"] for operacao in operacoes]
        self.assertIn("/items/0/name", caminhos)
        self.assertIn("/goals/0/title", caminhos)
        self.assertNotIn("/goals/0/hint", caminhos, "campo vazio nao entra no mod")
        self.assertEqual((mantidos, novos), (0, len(operacoes)))
        self.assertEqual(traducao.verificar(config, operacoes), [])

    def test_preserva_traducao_manual(self):
        config = {"items": [{"name": "House I"}]}
        anterior = {"/items/0/name": "Casa Numero Um"}
        operacoes, mantidos, novos = traducao.gerar(config, anterior)
        self.assertEqual(operacoes[0]["value"], "Casa Numero Um")
        self.assertEqual((mantidos, novos), (1, 0))

    def test_verificar_detecta_caminho_fora_do_config(self):
        config = {"items": [{"name": "House I"}]}
        ruim = [{"op": "replace", "path": "/items/99/name", "value": "x"}]
        self.assertEqual(traducao.verificar(config, ruim), ["/items/99/name"])

    def test_ativar_em_mods_txt_sem_quebra_de_linha_final(self):
        # O mods.txt do projeto original termina sem "\n": um append ingenuo
        # cola o nome no fim do ultimo comentario e o mod nunca carrega.
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "mods.txt")
            with open(caminho, "w", encoding="utf-8") as handle:
                handle.write("# comentario\n# no_hiring_needed")

            traducao.ativar_no_mods_txt(caminho, "ptbr")
            with open(caminho, encoding="utf-8") as handle:
                linhas = handle.read().splitlines()
            self.assertIn("ptbr", linhas)
            self.assertIn("# no_hiring_needed", linhas)

    def test_ativar_e_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "mods.txt")
            with open(caminho, "w", encoding="utf-8") as handle:
                handle.write("ptbr\n")
            traducao.ativar_no_mods_txt(caminho, "ptbr")
            with open(caminho, encoding="utf-8") as handle:
                self.assertEqual(handle.read().count("ptbr"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

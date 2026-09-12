"""Testes do SW Boost.

Rode com:  python -m unittest discover -s tests -v

Nenhum teste precisa dos arquivos do jogo: os SWF usados sao construidos na
hora e o modulo de saves e exercitado contra um `sessions` de mentira.
"""

from __future__ import annotations

import json
import os
import struct
import re
import sys
import tempfile
import types
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swboost import boost, console, saves, swf, tela, web  # noqa: E402
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


def _carregar_instalador():
    import importlib.util

    caminho = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "instalar.py"
    )
    spec = importlib.util.spec_from_file_location("instalar", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


instalador = _carregar_instalador()


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
# swboost.web - modo projector (jogar sem navegador)
# --------------------------------------------------------------------------


class TestProjectorUrl(unittest.TestCase):
    def _url(self, **kwargs):
        cfg = Settings(host="127.0.0.1", port=5055, **kwargs)
        return web.projector_url(
            cfg, "vila-1", "Basesec_1.5.4.swf", 1700000000,
            [{"uid": "2", "pic_square": "x.png"}],
        )

    def test_carrega_o_swloader_como_raiz(self):
        self.assertTrue(
            self._url().startswith(
                "http://127.0.0.1:5055/static/socialwars/flash/SWLoader.swf?"
            )
        )

    def test_leva_todos_os_parametros_que_o_jogo_le(self):
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(self._url()).query)
        # Sem navegador nao ha flashvars: tudo o que o play.html passaria
        # precisa estar na query string, que e de onde o Flash le.
        for chave in ("swftoload", "staticUrl", "dynamicUrl", "fb_sig_user",
                      "serverTime", "friendsInfo", "language", "user_key",
                      "skiphash12341", "spdebug", "accessToken"):
            self.assertIn(chave, query, f"faltou o parametro {chave}")
        self.assertEqual(query["fb_sig_user"], ["vila-1"])
        self.assertEqual(query["serverTime"], ["1700000000"])
        self.assertEqual(query["swftoload"], ["/static/socialwars/flash/Basesec_1.5.4.swf"])

    def test_friends_info_vai_como_json(self):
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(self._url()).query)
        self.assertEqual(json.loads(query["friendsInfo"][0]),
                         [{"uid": "2", "pic_square": "x.png"}])

    def test_codifica_valores_com_caracteres_especiais(self):
        # friendsInfo e JSON e vai cheio de aspas, chaves e dois-pontos.
        self.assertNotIn('{"uid"', self._url())

    def test_leva_o_fps_quando_o_turbo_esta_ligado(self):
        self.assertIn("_fps=60", self._url(fps=60))
        self.assertNotIn("_fps=", self._url(fps=0))


# --------------------------------------------------------------------------
# swboost.boost - build congelado (.exe)
# --------------------------------------------------------------------------


class TestCaminhosCongelados(unittest.TestCase):
    """O bundle.py do jogo aponta para sys._MEIPASS quando congelado.

    Como o nosso .exe e so o lancador (os assets ficam na pasta do jogo),
    sem correcao um build congelado procuraria os assets dentro da pasta
    temporaria do PyInstaller.
    """

    def setUp(self):
        self.bundle = types.ModuleType("bundle")
        self.bundle.TMP_BUNDLED_DIR = "/tmp/_MEIxxxx"
        self.bundle.ASSETS_DIR = "/tmp/_MEIxxxx/assets"
        self.bundle.TEMPLATES_DIR = "/tmp/_MEIxxxx/templates"
        self.bundle.VILLAGES_DIR = "/tmp/_MEIxxxx/villages"
        self.bundle.QUESTS_DIR = "/tmp/_MEIxxxx/villages/quest"
        self.bundle.CONFIG_DIR = "/tmp/_MEIxxxx/config"
        self.bundle.CONFIG_PATCH_DIR = "/tmp/_MEIxxxx/config/patch"
        self.bundle.STUB_DIR = "/tmp/_MEIxxxx/stub"
        sys.modules["bundle"] = self.bundle

    def tearDown(self):
        sys.modules.pop("bundle", None)
        if hasattr(sys, "frozen"):
            del sys.frozen

    def test_nao_mexe_em_nada_quando_nao_esta_congelado(self):
        self.assertFalse(boost.fix_bundle_paths("/jogo"))
        self.assertEqual(self.bundle.ASSETS_DIR, "/tmp/_MEIxxxx/assets")

    def test_redireciona_para_a_pasta_do_jogo_quando_congelado(self):
        sys.frozen = True
        self.assertTrue(boost.fix_bundle_paths(os.path.join(os.sep, "jogo")))

        raiz = os.path.join(os.sep, "jogo")
        self.assertEqual(self.bundle.ASSETS_DIR, os.path.join(raiz, "assets"))
        self.assertEqual(self.bundle.TEMPLATES_DIR, os.path.join(raiz, "templates"))
        self.assertEqual(self.bundle.VILLAGES_DIR, os.path.join(raiz, "villages"))
        self.assertEqual(self.bundle.QUESTS_DIR, os.path.join(raiz, "villages", "quest"))
        self.assertEqual(self.bundle.CONFIG_DIR, os.path.join(raiz, "config"))
        self.assertEqual(self.bundle.CONFIG_PATCH_DIR,
                         os.path.join(raiz, "config", "patch"))
        self.assertEqual(self.bundle.STUB_DIR, os.path.join(raiz, "stub"))
        self.assertNotIn("_MEI", self.bundle.ASSETS_DIR)


# --------------------------------------------------------------------------
# swboost.tela - Full HD, 2K e a janela inteira
# --------------------------------------------------------------------------


class TestResolucao(unittest.TestCase):
    def test_presets_conhecidos(self):
        for chave in ("janela", "1920x1080", "2560x1440", "3840x2160", "original"):
            self.assertEqual(tela.normalizar_resolucao(chave), chave)

    def test_janela_nao_fixa_dimensao(self):
        self.assertEqual(tela.dimensoes("janela"), (None, None))

    def test_full_hd_e_2k(self):
        self.assertEqual(tela.dimensoes("1920x1080"), (1920, 1080))
        self.assertEqual(tela.dimensoes("2560x1440"), (2560, 1440))

    def test_aceita_medida_personalizada(self):
        self.assertEqual(tela.normalizar_resolucao("1720x960"), "1720x960")
        self.assertEqual(tela.dimensoes("1720x960"), (1720, 960))

    def test_recusa_lixo_e_volta_ao_padrao(self):
        for ruim in ("", None, "enorme", "99999x99999", "10x10", "axb", "1920x"):
            self.assertEqual(tela.normalizar_resolucao(ruim), tela.RESOLUCAO_PADRAO)


class TestPaginaDoJogo(unittest.TestCase):
    SAVE = {"userid": "vila-1", "name": "Minha Vila", "level": 12}
    AMIGOS = [{"uid": "2", "pic_square": "http://x/y.png"}]

    def _pagina(self, **kwargs):
        return tela.render(
            base_url="http://127.0.0.1:5055", save_info=self.SAVE,
            gameversion="Basesec_1.5.4.swf", server_time=1700000000,
            friends_info=self.AMIGOS, **kwargs,
        )

    def _embed(self, pagina):
        return re.search(r"<embed\b.*?>", pagina, re.S | re.I).group(0)

    def test_janela_usa_cem_por_cento(self):
        tag = self._embed(self._pagina(resolucao="janela"))
        self.assertIn('width="100%"', tag)
        self.assertIn('height="100%"', tag)

    def test_resolucao_fixa_vai_para_o_embed(self):
        tag = self._embed(self._pagina(resolucao="2560x1440"))
        self.assertIn('width="2560"', tag)
        self.assertIn('height="1440"', tag)

    def test_leva_os_mesmos_parametros_do_play_html_original(self):
        # Se a lista divergir do template original, o jogo carrega diferente.
        from urllib.parse import parse_qs
        import html as H

        tag = self._embed(self._pagina(resolucao="1920x1080"))
        fv = H.unescape(re.search(r'flashvars="([^"]*)"', tag).group(1))
        query = parse_qs(fv)
        for chave in ("staticUrl", "dynamicUrl", "fb_sig_user", "serverTime",
                      "friendsInfo", "language", "user_key", "skiphash12341",
                      "spdebug", "accessToken", "sex", "lastLoggedIn",
                      "dailyBonus", "forceSyncError", "forceAttackReload",
                      "forceQuestReload"):
            self.assertIn(chave, query, f"faltou o flashvar {chave}")
        self.assertEqual(query["fb_sig_user"], ["vila-1"])

    def test_carrega_o_swloader_com_a_versao_escolhida(self):
        tag = self._embed(self._pagina())
        self.assertIn("SWLoader.swf?swftoload=", tag)
        self.assertIn("Basesec_1.5.4.swf", tag)

    def test_permite_tela_cheia_do_flash(self):
        # O jogo tem toggleFullscreen embutido; sem este atributo ele nao roda.
        self.assertIn('allowFullScreen="true"', self._embed(self._pagina()))

    def test_leva_o_fps_do_modo_turbo(self):
        self.assertIn("_fps=60", self._embed(self._pagina(fps=60)))
        self.assertNotIn("_fps=", self._embed(self._pagina(fps=0)))

    def test_wmode_so_aparece_quando_pedido(self):
        self.assertNotIn("wmode", self._embed(self._pagina()))
        self.assertIn('wmode="direct"', self._embed(self._pagina(wmode="direct")))

    def test_escapa_nome_de_vila_com_html(self):
        pagina = tela.render(
            base_url="http://127.0.0.1:5055",
            save_info={"userid": "v", "name": "<script>alert(1)</script>", "level": 1},
            gameversion="Basesec_1.5.4.swf", server_time=1, friends_info=[],
        )
        self.assertNotIn("<script>alert(1)</script>", pagina)
        self.assertIn("&lt;script&gt;", pagina)

    def test_pagina_ocupa_a_janela_toda(self):
        pagina = self._pagina(resolucao="janela")
        self.assertIn("height: 100%", pagina)
        self.assertIn("margin: 0", pagina)


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


# --------------------------------------------------------------------------
# instalar.py - caminho digitado ou arrastado pelo usuario
# --------------------------------------------------------------------------


class TestCaminhoDigitado(unittest.TestCase):
    """Arrastar uma pasta para o terminal nao entrega um caminho limpo."""

    def test_tira_aspas_do_arrastar_no_prompt(self):
        # O Prompt de Comando poe aspas quando o caminho tem espaco.
        self.assertEqual(
            instalador._limpar_caminho('"C:\\Users\\Aula\\Meus Videos\\jogo"'),
            "C:\\Users\\Aula\\Meus Videos\\jogo",
        )

    def test_tira_o_e_comercial_do_powershell(self):
        self.assertEqual(
            instalador._limpar_caminho('& "C:\\pasta\\jogo"'), "C:\\pasta\\jogo"
        )

    def test_tira_barra_do_fim(self):
        self.assertEqual(instalador._limpar_caminho("C:\\jogo\\"), "C:\\jogo")
        self.assertEqual(instalador._limpar_caminho("/home/user/jogo/"), "/home/user/jogo")

    def test_tira_espacos_em_volta(self):
        self.assertEqual(instalador._limpar_caminho("   /home/user/jogo  "), "/home/user/jogo")

    def test_resposta_vazia_continua_vazia(self):
        # Enter sem digitar nada significa desistir.
        self.assertEqual(instalador._limpar_caminho("   "), "")

    def test_nao_estraga_um_caminho_ja_limpo(self):
        self.assertEqual(instalador._limpar_caminho("/home/user/jogo"), "/home/user/jogo")


# --------------------------------------------------------------------------
# funcionar antes de o Flask existir
# --------------------------------------------------------------------------


BLOQUEIO_FLASK = """
import sys

class SemFlask:
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome == "flask" or nome.startswith("flask."):
            raise ImportError("No module named 'flask'")
        return None

sys.meta_path.insert(0, SemFlask())
sys.path.insert(0, {raiz!r})
"""


class TestSemFlaskInstalado(unittest.TestCase):
    """O instalador e o --check rodam antes de qualquer pip install.

    Regressao: `instalar.py` importava `swboost.boost`, que importa
    `swboost.web`, que importa Flask - e o instalador, que so copia arquivos,
    morria com ModuleNotFoundError numa maquina limpa. O `--check`, que existe
    para dizer o que falta instalar, quebrava do mesmo jeito.
    """

    def setUp(self):
        self.raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _rodar(self, codigo: str):
        import subprocess

        script = BLOQUEIO_FLASK.format(raiz=self.raiz) + codigo
        return subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=self.raiz, timeout=60,
        )

    def test_o_bloqueio_do_teste_funciona(self):
        # Sem isto, o teste passaria por acidente numa maquina com Flask.
        saida = self._rodar("import flask")
        self.assertNotEqual(saida.returncode, 0)
        self.assertIn("No module named 'flask'", saida.stderr)

    def test_gamedir_nao_depende_de_flask(self):
        saida = self._rodar(
            "from swboost.gamedir import locate_game_dir, port_is_free, BoostError\n"
            "print('ok')"
        )
        self.assertEqual(saida.returncode, 0, saida.stderr)
        self.assertIn("ok", saida.stdout)

    def test_instalador_importa_sem_flask(self):
        saida = self._rodar(
            "import importlib.util, os\n"
            f"spec = importlib.util.spec_from_file_location('instalar', os.path.join({self.raiz!r}, 'instalar.py'))\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(m)\n"
            "print('ok', callable(m.main))"
        )
        self.assertEqual(saida.returncode, 0, saida.stderr)
        self.assertIn("ok True", saida.stdout)

    def test_check_diagnostica_em_vez_de_quebrar(self):
        saida = self._rodar(
            "import importlib.util, os, sys\n"
            f"spec = importlib.util.spec_from_file_location('play', os.path.join({self.raiz!r}, 'play.py'))\n"
            "m = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(m)\n"
            "sys.exit(0 if callable(m.run_check) else 1)"
        )
        self.assertEqual(saida.returncode, 0, saida.stderr)
        self.assertNotIn("ModuleNotFoundError", saida.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

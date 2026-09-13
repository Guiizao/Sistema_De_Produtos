"""Tela de entrada: escolher a vila, a resolucao e a taxa de quadros.

Substitui o `templates/login.html` do projeto original, que so deixava
escolher a vila e a versao do jogo. As escolhas de resolucao e de taxa de
quadros ficam na sessao e valem para a partida, sem reiniciar o servidor.

Traz tambem o aviso de Flash ausente. Sem ele, um navegador moderno (Chrome,
Edge, Firefox atual) mostra apenas uma tela preta: o `<embed>` do Flash nao
renderiza nada e nao existe mensagem de erro nenhuma. O aviso explica o que
esta acontecendo em vez de deixar o jogador no escuro.
"""

from __future__ import annotations

import html

from .tela import AVISO_FLASH_JS, RESOLUCOES, RESOLUCAO_PADRAO

# O Flash Player nunca passou de 120 fps. 30 e o valor de fabrica do jogo.
TAXAS = (
    (0, "30 fps - original (recomendado)"),
    (60, "60 fps - turbo, jogo 2x mais rapido"),
    (120, "120 fps - turbo, jogo 4x mais rapido"),
)

ESTILO = """
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; min-height: 100vh;
    background: #10130a; color: #f2edc4;
    font-family: 'lucida grande', tahoma, verdana, arial, sans-serif;
    font-size: 14px;
    display: flex; align-items: center; justify-content: center;
    padding: 24px;
  }
  .caixa {
    width: 100%; max-width: 460px;
    background: #1c210b; border: 1px solid #414603; border-radius: 10px;
    padding: 26px 28px 22px;
  }
  .topo { text-align: center; margin-bottom: 22px; }
  .topo img { width: 190px; max-width: 100%; }
  .topo p { margin: 8px 0 0; color: #8d9264; font-size: 12px; }
  label { display: block; margin: 16px 0 6px; font-weight: bold; color: #e9dd51; }
  select {
    width: 100%; padding: 9px 10px;
    background: #2a2f0c; color: #f9face;
    border: 1px solid #616807; border-radius: 5px; font-size: 14px;
  }
  select:focus { outline: 2px solid #8d9612; outline-offset: 1px; }
  .nota { margin: 5px 0 0; color: #8d9264; font-size: 12px; }
  button {
    width: 100%; margin-top: 22px; padding: 12px;
    background: #616807; color: #fffde3;
    border: 1px solid #8d9612; border-radius: 6px;
    font-size: 16px; font-weight: bold; cursor: pointer;
  }
  button:hover { background: #7b8409; }
  .rodape { margin-top: 18px; text-align: center; font-size: 13px; }
  a { color: #e9dd51; }
  .alerta {
    margin-bottom: 18px; padding: 12px 14px;
    background: #3a2410; border: 1px solid #8a5a1e; border-radius: 6px;
    color: #ffd9a8; font-size: 13px; line-height: 1.5;
  }
  .alerta b { color: #ffb457; }
"""


def _opcoes_resolucao(escolhida: str) -> str:
    saida = []
    for valor, (rotulo, _l, _a) in RESOLUCOES.items():
        marcado = " selected" if valor == escolhida else ""
        saida.append(f'<option value="{valor}"{marcado}>{html.escape(rotulo)}</option>')
    return "".join(saida)


def _opcoes_taxa(escolhida: int) -> str:
    saida = []
    for valor, rotulo in TAXAS:
        marcado = " selected" if valor == escolhida else ""
        saida.append(f'<option value="{valor}"{marcado}>{html.escape(rotulo)}</option>')
    return "".join(saida)


def render(saves_info: list, versao: str, resolucao: str = RESOLUCAO_PADRAO,
           fps: int = 0, versoes: tuple = ("Basesec_1.5.4.swf",)) -> str:
    """Monta a tela de entrada."""
    vilas = "".join(
        f'<option value="{html.escape(str(s["userid"]))}">'
        f'{html.escape(str(s["name"]))} - nivel {html.escape(str(s["level"]))} '
        f'({html.escape(str(s["xp"]))} xp)</option>'
        for s in saves_info
    )
    opcoes_versao = "".join(
        f'<option value="{html.escape(v)}">{html.escape(v.replace("Basesec_", "").replace(".swf", ""))}</option>'
        for v in versoes
    )

    if saves_info:
        formulario = f"""
      <form method="post">
        <label for="USERID">Vila</label>
        <select id="USERID" name="USERID" required>{vilas}</select>

        <label for="res">Resolucao</label>
        <select id="res" name="res">{_opcoes_resolucao(resolucao)}</select>
        <p class="nota">"Preencher a janela" usa o tamanho do navegador.
           Maximize para jogar em Full HD ou 2K.</p>

        <label for="fps">Taxa de quadros</label>
        <select id="fps" name="fps">{_opcoes_taxa(fps)}</select>
        <p class="nota">No Social Wars a taxa de quadros controla a
           <b>velocidade</b> do jogo, nao a suavidade. 60 fps deixa unidades,
           combate e animacoes 2x mais rapidos. A producao de recursos nao muda.</p>

        <label for="GAMEVERSION">Versao do jogo</label>
        <select id="GAMEVERSION" name="GAMEVERSION" required>{opcoes_versao}</select>

        <button type="submit">Jogar</button>
      </form>
      <p class="rodape">ou <a href="/new.html">criar uma vila nova</a></p>"""
    else:
        formulario = """
      <p class="nota" style="text-align:center; margin:24px 0;">
        Nenhuma vila salva ainda.
      </p>
      <p class="rodape"><a href="/new.html"><b>Criar a primeira vila</b></a></p>"""

    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Social Wars</title>
<link rel="shortcut icon" href="/img/icon.png">
<style>{ESTILO}</style>
</head>
<body>
  <div class="caixa">
    <div class="topo">
      <img src="/img/logo.png" alt="Social Wars">
      <p>Social Warriors ~ {html.escape(str(versao))}</p>
    </div>

    <div class="alerta" id="semflash" style="display:none">
      <b>Este navegador nao tem Flash.</b><br>
      O jogo e em Flash, entao aqui a tela vai ficar preta - sem erro nenhum,
      so preta. Voce precisa de um navegador com Flash, como o
      <a href="https://github.com/radubirsan/FlashBrowser/releases/latest"
         target="_blank" rel="noopener">FlashBrowser</a>.<br><br>
      Abra <b>este mesmo endereco</b> nele:
      <b><span id="url"></span></b>
    </div>

{formulario}
  </div>

<script>
{AVISO_FLASH_JS}
if (!temFlash()) {{
  document.getElementById('url').textContent = location.origin + '/';
  document.getElementById('semflash').style.display = 'block';
}}
</script>
</body>
</html>
"""

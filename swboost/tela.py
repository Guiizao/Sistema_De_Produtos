"""Pagina do jogo em tela cheia, Full HD e 2K.

O Social Wars nunca foi limitado a 760x600 - quem limita e o `<embed>` do
`templates/play.html`, que fixa 760x600 (o JavaScript da pagina depois estica
a largura para 1090, mas nunca mexe na altura).

O jogo em si ja e preparado para qualquer resolucao:

- `stage.scaleMode = NO_SCALE`, entao uma area maior mostra MAIS MAPA em vez
  de esticar a imagem - nada fica borrado;
- `GuiManager.widescreen()` ancora a HUD nas bordas a partir de
  `stage.stageWidth`/`stageHeight`: barra de baixo em `stageHeight - 125`,
  slider de zoom em `stageWidth - 24`, objetivos a esquerda;
- `GuiManager` escuta `Event.RESIZE` e `FullScreenEvent.FULL_SCREEN` e chama
  `onWidescreenChange()`, que reposiciona HUD, popups e fundo;
- `Base.resizeBGColor()` redesenha o fundo no tamanho do palco.

Ou seja: basta dar espaco ao plugin. Esta pagina faz isso.
"""

from __future__ import annotations

import html
import json


# Resolucoes oferecidas no seletor. "janela" acompanha o tamanho do navegador,
# que e o que realmente entrega Full HD/2K no monitor de quem joga.
RESOLUCOES = {
    "janela": ("Preencher a janela", None, None),
    "1366x768": ("1366 x 768", 1366, 768),
    "1600x900": ("1600 x 900", 1600, 900),
    "1920x1080": ("Full HD - 1920 x 1080", 1920, 1080),
    "2560x1440": ("2K - 2560 x 1440", 2560, 1440),
    "3840x2160": ("4K - 3840 x 2160", 3840, 2160),
    "original": ("Original - 1090 x 600", 1090, 600),
}

RESOLUCAO_PADRAO = "janela"

# Bloco compartilhado com a pagina do jogo: detecta a falta de Flash e diz o
# que fazer. A checagem e um palpite (nem todo navegador com Flash anuncia o
# mimetype do mesmo jeito), entao o aviso nunca bloqueia nada - da para
# fechar e seguir.
AVISO_FLASH_JS = """
function temFlash() {
  try {
    if (navigator.mimeTypes && navigator.mimeTypes['application/x-shockwave-flash']) return true;
    if (navigator.plugins) {
      for (var i = 0; i < navigator.plugins.length; i++) {
        var nome = (navigator.plugins[i].name || '').toLowerCase();
        if (nome.indexOf('flash') !== -1 || nome.indexOf('shockwave') !== -1) return true;
      }
    }
    if (window.ActiveXObject) {
      try { new window.ActiveXObject('ShockwaveFlash.ShockwaveFlash'); return true; } catch (e) {}
    }
  } catch (e) { return true; }  /* na duvida, nao atrapalha */
  return false;
}
"""


# Mesmos flashvars do templates/play.html do projeto original. O `brk=0` entre
# os parametros nao e lido pelo jogo, mas fica para manter o formato identico
# ao que ja funciona hoje.
FLASHVARS_FIXOS = (
    ("spdebug", "notnull"),
    ("skiphash12341", "notnull"),
    ("user_key", "123456789"),
    ("language", "en"),
    ("accessToken",
     "AAABbZAm0wdMUBALsOrR0Ho68CLjaOT8SV3vftKg9mbo1zZColaW5FljRVaLxPGxXXnm1M98"
     "mTZCAttcQ4GHwvSyXfsyxYmvKMH8Hmn5iliSPnjvIsZA6"),
    ("sex", "m"),
    ("lastLoggedIn", "1349266517"),
    ("dailyBonus", "0"),
    ("forceSyncError", "1"),
    ("forceAttackReload", "0"),
    ("forceQuestReload", "0"),
)


def normalizar_resolucao(valor: str | None) -> str:
    """Devolve uma chave valida de RESOLUCOES, aceitando 'LARGURAxALTURA'."""
    if not valor:
        return RESOLUCAO_PADRAO
    valor = valor.strip().lower()
    if valor in RESOLUCOES:
        return valor

    # Resolucao personalizada, tipo "1720x960".
    if "x" in valor:
        largura, _, altura = valor.partition("x")
        try:
            largura, altura = int(largura), int(altura)
        except ValueError:
            return RESOLUCAO_PADRAO
        if 320 <= largura <= 7680 and 240 <= altura <= 4320:
            return f"{largura}x{altura}"
    return RESOLUCAO_PADRAO


def dimensoes(chave: str) -> tuple:
    """(largura, altura) em pixels, ou (None, None) para 'preencher a janela'."""
    if chave in RESOLUCOES:
        return RESOLUCOES[chave][1], RESOLUCOES[chave][2]
    largura, _, altura = chave.partition("x")
    return int(largura), int(altura)


def montar_flashvars(base_url: str, userid: str, server_time: int,
                     friends_info: list) -> str:
    """Monta a string de flashvars, no mesmo formato do play.html original."""
    pares = [
        ("staticUrl", f"{base_url}/static/socialwars/"),
        ("dynamicUrl", f"{base_url}/dynamic/menvswomen/srvsexwars/"),
        ("fb_sig_user", str(userid)),
        ("friendsInfo", json.dumps(friends_info)),
        ("serverTime", str(server_time)),
        *FLASHVARS_FIXOS,
    ]
    return "&brk=0&".join(f"{chave}={valor}" for chave, valor in pares)


def montar_src(base_url: str, gameversion: str, fps: int = 0) -> str:
    src = (f"{base_url}/static/socialwars/flash/SWLoader.swf"
           f"?swftoload=/static/socialwars/flash/{gameversion}")
    if fps:
        src += f"&_fps={fps}"
    return src


def render(base_url: str, save_info: dict, gameversion: str, server_time: int,
           friends_info: list, resolucao: str = RESOLUCAO_PADRAO,
           fps: int = 0, wmode: str = "") -> str:
    """Devolve a pagina completa do jogo."""
    chave = normalizar_resolucao(resolucao)
    largura, altura = dimensoes(chave)
    encaixa_na_janela = largura is None

    src = html.escape(montar_src(base_url, gameversion, fps), quote=True)
    flashvars = html.escape(
        montar_flashvars(base_url, save_info.get("userid", ""), server_time, friends_info),
        quote=True,
    )

    dim_embed = ('width="100%" height="100%"' if encaixa_na_janela
                 else f'width="{largura}" height="{altura}"')
    attr_wmode = f' wmode="{html.escape(wmode, quote=True)}"' if wmode else ""

    opcoes = []
    for valor, (rotulo, _l, _a) in RESOLUCOES.items():
        marcado = " selected" if valor == chave else ""
        opcoes.append(f'<option value="{valor}"{marcado}>{html.escape(rotulo)}</option>')
    if chave not in RESOLUCOES:
        opcoes.append(f'<option value="{chave}" selected>{html.escape(chave)} (personalizada)</option>')

    nome = html.escape(str(save_info.get("name", "Jogador")))
    nivel = html.escape(str(save_info.get("level", "?")))
    info_fps = f"{fps} fps (turbo)" if fps else "30 fps"

    return f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Social Wars</title>
<link rel="shortcut icon" href="/img/icon.png">
<style>
  html, body {{
    margin: 0; padding: 0; width: 100%; height: 100%;
    background: #10130a; overflow: hidden;
    font-family: 'lucida grande', tahoma, verdana, arial, sans-serif;
  }}
  /* O palco centraliza o jogo. Em resolucao fixa maior que a janela, vira
     area rolavel em vez de cortar a HUD. */
  #palco {{
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    overflow: {"hidden" if encaixa_na_janela else "auto"};
  }}
  #jogo {{ display: block; line-height: 0; }}
  /* Faixa fina no topo: passar o mouse revela a barra, para nao roubar
     espaco de tela do jogo. */
  #gatilho {{ position: fixed; top: 0; left: 0; right: 0; height: 8px; z-index: 20; }}
  #barra {{
    position: fixed; top: 0; left: 0; right: 0; z-index: 21;
    display: flex; align-items: center; gap: 16px;
    padding: 6px 14px; box-sizing: border-box;
    background: rgba(16, 19, 10, .94);
    border-bottom: 1px solid #414603;
    color: #e9dd51; font-size: 12px;
    transform: translateY(-100%); transition: transform .18s ease;
  }}
  #gatilho:hover ~ #barra, #barra:hover {{ transform: translateY(0); }}
  #barra a, #barra label {{ color: #e9dd51; text-decoration: none; }}
  #barra a:hover {{ text-decoration: underline; }}
  #barra select {{
    background: #2a2f0c; color: #f9face; border: 1px solid #616807;
    border-radius: 3px; padding: 2px 4px; font-size: 12px;
  }}
  .espaco {{ margin-left: auto; }}
  .dica {{ color: #8a8f5e; }}
  /* Aviso de Flash ausente: sem ele, o jogador so ve uma tela preta. */
  #semflash {{
    display: none; position: fixed; inset: 0; z-index: 30;
    background: rgba(16, 19, 10, .97); color: #f2edc4;
    padding: 32px; overflow: auto;
    flex-direction: column; align-items: center; justify-content: center;
    text-align: center; line-height: 1.6;
  }}
  #semflash h2 {{ color: #ffb457; margin: 0 0 14px; }}
  #semflash p {{ margin: 0 0 12px; max-width: 560px; }}
  #semflash .url {{
    font-family: consolas, monospace; font-size: 16px; color: #e9dd51;
    background: #2a2f0c; border: 1px solid #616807; border-radius: 5px;
    padding: 8px 14px;
  }}
  #semflash .miudo {{ color: #8a8f5e; font-size: 12px; }}
  #semflash a {{ color: #e9dd51; }}
  #semflash button {{
    margin-top: 18px; padding: 9px 16px; cursor: pointer;
    background: #2a2f0c; color: #f2edc4;
    border: 1px solid #616807; border-radius: 5px; font-size: 13px;
  }}
</style>
</head>
<body>
  <div id="palco">
    <object id="jogo">
      <embed id="swf" src="{src}"
        allowFullScreen="true" bgcolor="#669C2C" quality="high"
        {dim_embed}{attr_wmode} name="se"
        type="application/x-shockwave-flash"
        pluginspage="http://www.macromedia.com/go/getflashplayer"
        flashvars="{flashvars}">
    </object>
  </div>

  <div id="semflash">
    <h2>Este navegador nao tem Flash</h2>
    <p>O Social Wars e um jogo em Flash. Sem um navegador que rode Flash, esta
       tela fica preta - sem mensagem de erro, so preta.</p>
    <p><b>O que fazer:</b> instale o
       <a href="https://github.com/radubirsan/FlashBrowser/releases/latest"
          target="_blank" rel="noopener">FlashBrowser</a>
       e abra neste endereco:</p>
    <p class="url" id="url"></p>
    <p class="miudo">O servidor aqui continua rodando normalmente - o que falta
       e so o Flash do lado do navegador.</p>
    <button type="button" id="fechar">Fechar e continuar mesmo assim</button>
  </div>

  <div id="gatilho"></div>
  <div id="barra">
    <b>{nome}</b> &middot; nivel {nivel}
    <label>Resolucao
      <select id="res">{''.join(opcoes)}</select>
    </label>
    <span class="dica">{info_fps}</span>
    <span class="dica">Tela cheia: botao de opcoes dentro do jogo</span>
    <a class="espaco" href="/">Trocar de vila</a>
  </div>

<script>
{AVISO_FLASH_JS}
(function () {{
  // Navegador sem Flash mostra so preto. Melhor explicar do que deixar no escuro.
  if (!temFlash()) {{
    document.getElementById('url').textContent = location.origin + '/';
    var painel = document.getElementById('semflash');
    painel.style.display = 'flex';
    document.getElementById('fechar').onclick = function () {{
      painel.style.display = 'none';
    }};
  }}

  var seletor = document.getElementById('res');

  // A escolha fica no navegador: o servidor nao precisa guardar estado.
  try {{
    var salva = localStorage.getItem('swboost.resolucao');
    var atual = new URLSearchParams(location.search).get('res');
    if (salva && !atual && salva !== {chave!r}) {{
      location.replace('?res=' + encodeURIComponent(salva));
      return;
    }}
  }} catch (e) {{ /* modo privado ou storage bloqueado: segue sem lembrar */ }}

  seletor.addEventListener('change', function () {{
    try {{ localStorage.setItem('swboost.resolucao', seletor.value); }} catch (e) {{}}
    location.href = '?res=' + encodeURIComponent(seletor.value);
  }});
}})();
</script>
</body>
</html>
"""

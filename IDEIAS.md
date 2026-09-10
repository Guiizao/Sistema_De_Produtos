# Ideias para o Social Wars — o que ainda dá para melhorar

Lista feita a partir da leitura do servidor Python e da descompilação do jogo
(ver [`ANALISE_TECNICA.md`](ANALISE_TECNICA.md)). Cada item traz o esforço
estimado e o risco real de quebrar alguma coisa.

Legenda: 🟢 baixo risco · 🟡 exige cuidado · 🔴 pode quebrar o jogo

---

## Já entregue neste repositório

| | O que |
| --- | --- |
| ✅ | Início com um clique, com detecção de navegador Flash |
| ✅ | Entrar direto na última vila (sem tela de login) |
| ✅ | Cache de assets no navegador (2ª partida não pede nada) |
| ✅ | Configuração do jogo comprimida e em cache (1 MB → 60 KB) |
| ✅ | Servidor HTTP multi-thread (waitress) |
| ✅ | Gravação de save atômica + backups rotativos |
| ✅ | Modo turbo 60/120 fps, opcional e reversível |
| ✅ | `requirements.txt` corrigido |
| ✅ | Ferramenta de benchmark e de taxa de quadros |
| ✅ | Gerador de mod de tradução (`ferramentas/gerar_mod_traducao.py`) |
| ✅ | Executável (`SocialWars.exe`) que dispensa ter Python instalado |
| ✅ | Instalação sem administrador (ambiente virtual dentro da pasta do jogo) |
| ✅ | Modo projector: jogar sem navegador nenhum |

---

## 1. Tradução para português

🟢 **Baixo risco**

**O jogo já foi feito para isso.** `core/Language.as` declara
`LANGUAGE_BRASILIAN = "br"` ao lado de espanhol, italiano, francês, alemão,
turco, grego — e klingon.

Existem dois caminhos, com dificuldades bem diferentes:

**Caminho fácil — textos que vêm do servidor.** Nomes de construções e
unidades (`items[].name`), e os objetivos (`goals[].title`, `.hint`,
`.description`) estão todos no `config/main.json`. Dá para traduzir **sem
tocar no SWF**, usando o sistema de mods que o projeto já tem (jsonpatch).

Este repositório traz o gerador do esqueleto:

```bash
python ferramentas/gerar_mod_traducao.py --saida mods/ptbr.json
# depois: adicione "ptbr" no arquivo mods/mods.txt
```

**Caminho difícil — textos dentro do SWF.** Os textos da interface passam por
`Language.getLiteral(...)` e viriam de um catálogo gettext (`.mo`). Só que a
URL base do catálogo está fixa no código, apontando para um domínio da Social
Point que não existe mais:

```actionscript
_loc1_.translation(Base.Main.getTextUrl,
   "http://dynamic.flash1.dev.socialpoint.es/appsfb/socialwarsdev/locale/", language);
```

Para usar, seria preciso redirecionar esse domínio para o servidor local
(arquivo `hosts`) ou trocar a string dentro do SWF. Viável — a string nova é
mais curta que a original, e o formato ABC é indexado, não baseado em
deslocamentos de byte — mas é um trabalho à parte.

---

## 2. Reativar a casa de leilões

🟢 **Baixo risco**

O `server.py` tem três rotas inteiras (`get_bets_list`, `get_bet_detail`,
`set_bet`) e o `auctions.py` completo — tudo comentado. Existe até um
`config/auctionhouse.json`. É funcionalidade pronta esperando um teste.

**Esforço:** algumas horas de teste. **Risco:** baixo — se der errado, é só
comentar de novo.

---

## 3. Jogar com amigos na mesma rede

🟢 **Baixo risco**

O servidor escuta só em `127.0.0.1`. Trocar para `0.0.0.0` (já é possível com
`--host 0.0.0.0`) permite que outra pessoa na mesma rede entre pelo IP da sua
máquina. O jogo já tem sistema de vizinhos, visitas e presentes, e o
`sessions.fb_friends_str()` já monta a lista de amigos a partir dos saves.

Faltaria: uma tela de login que mostre as vilas de forma decente e uma
sessão por pessoa (hoje a chave secreta do Flask é a string fixa
`'SECRET_KEY'`, o que é irrelevante em `localhost` mas não numa rede).

---

## 4. Mods de jogabilidade pelo config

🟢 **Baixo risco**

Todo o balanceamento vem do `config/main.json`, e o sistema de mods aplica
patches JSON em cima. Já existe um exemplo (`no_hiring_needed.json`).
Alguns `globals` interessantes que dá para mexer sem tocar no jogo:

| Chave | Efeito |
| --- | --- |
| `MAX_POPULATION_CAP`, `MAX_POPULATION_PER_LEVEL` | teto de população |
| `TIMER_HARVEST` | ritmo da colheita |
| `MAX_MINES_GOLD`, `MAX_MINES_WOOD`, ... | limite de minas |
| `SPYINGS_MAX` | espionagens por dia |
| `BUILD_SPEEDUP_MIN_TIME` | quando o acelerar fica disponível |
| `MARKET_MAX_NUM_TRADES` | trocas por dia no mercado |

Ideia de pacote: um mod **"sandbox"** (recursos fartos, sem espera) e um mod
**"hardcore"** (custos maiores, população menor), cada um em um arquivo, para
o jogador escolher no `mods.txt`.

---

## 5. Painel de administração pelo navegador

🟡 **Exige cuidado**

O jogo já tem um painel de depuração completo escondido: digitar
**SARANDONGA** durante a partida libera comandos como `give` (recursos),
`ff` (avançar o tempo), `spawn`, `loadMap` e botões para abrir qualquer
quest. (Também tem dois ovos de páscoa: o Konami Code liga balões de fala, e
**A B A C A B B** liga o "blood mode".)

O que faltaria é um painel **do lado do servidor** — uma página web para
editar recursos, nível e itens da vila com o jogo fechado, mexendo direto no
save. Mais seguro que o painel do cliente, porque o servidor valida e grava
de forma atômica.

---

## 6. 60 fps de verdade

🔴 **Pode quebrar o jogo**

Descrito em detalhe na [análise](ANALISE_TECNICA.md#o-que-seria-preciso-para-60-fps-de-verdade).
Resumo: exigiria reescrever o laço de jogo em ActionScript para separar
simulação (30 Hz) de renderização (60 Hz), desacoplar as animações de ~860
SWF de sprites e interpolar posições.

É o item de maior risco da lista e o de menor retorno por hora de trabalho.
O modo turbo já entregue cobre quem quer o jogo mais ágil.

---

## 7. Dispensar o navegador com o Flash projector

✅ **Entregue** — falta só a confirmação em uma máquina com Flash

O Flash Player standalone (projector) abre um SWF por URL e lê os parâmetros
da query string — que é de onde o jogo tira `staticUrl`, `dynamicUrl`,
`fb_sig_user` e companhia. Isso resolve o maior obstáculo de instalação: dá
para jogar **sem navegador nenhum**.

Implementado em `play.py --projector`: a rota `/swboost/projector` monta a URL
com os 17 parâmetros e o `browsers.py` procura o projector na máquina —
inclusive o `FlashPlayerApp.exe` que o instalador do Flash ActiveX deixa no
Windows.

O que falta: **abrir o Flash de verdade para confirmar**. A URL está testada
(o SWF é servido corretamente, com o MIME certo e todos os parâmetros), mas o
ambiente de desenvolvimento é Linux sem Flash Player. Se o sandbox de
segurança do Flash reclamar de algo, é aqui que vai aparecer.

---

## 8. Ruffle

🔴 **Pode quebrar o jogo**

O [Ruffle](https://ruffle.rs) roda SWF sem Flash Player. Hoje o suporte a
ActionScript 3 ainda é parcial, e o Social Wars é AS3 pesado — é bem
improvável que funcione agora. Vale reavaliar de tempos em tempos: no dia em
que funcionar, o jogo roda em qualquer navegador moderno e o problema de
instalação acaba.

---

## 9. Melhorias de conforto

🟢 **Baixo risco**

- **Atalho na área de trabalho** criado pelo instalador (Windows).
- **Tela inicial melhor**: a `login.html` atual é bem crua. Cartões com
  miniatura da vila, nível e último acesso.
- **Botão de tela cheia** de verdade na página do jogo (hoje o "Expand" só
  estica a largura para 100%). Como o palco é `NO_SCALE`, uma janela maior
  mostra mais mapa — não borra nada.
- **Exportar/importar vila**: um `.zip` com o save para trocar com amigos ou
  guardar antes de testar mods.
- **Save automático periódico**: hoje só grava quando o cliente manda
  comandos.

---

## 10. Robustez do servidor

🟡 **Exige cuidado**

- `command.py` faz `assert data_str[64] == ';'`: um pacote malformado derruba
  a requisição com erro 500 em vez de uma mensagem clara.
- `load_saves()` roda a cada visita à página de login, relendo todos os saves
  do disco. É proposital (permite editar saves sem reiniciar), mas com muitas
  vilas fica caro — daria para checar a data de modificação dos arquivos.
- `get_player_info` e `command.php` não têm tratamento de erro: uma exceção
  em qualquer comando aborta o lote inteiro, e o que já foi processado não é
  gravado.
- Migração de saves (`version.py`) só cobre 0.01a → 0.02a. Convém deixar a
  cadeia preparada para as próximas versões.

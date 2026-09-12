# Manual do SW Boost

Referência completa. Para simplesmente jogar, o [README](README.md) basta.

---

## Índice

- [Como funciona](#como-funciona)
- [Opções do lançador](#opções-do-lançador)
- [Arquivo de configuração](#arquivo-de-configuração)
- [Desempenho medido](#desempenho-medido)
- [Resolução: Full HD, 2K e 4K](#resolução-full-hd-2k-e-4k)
- [Modo turbo em detalhe](#modo-turbo-em-detalhe)
- [Tradução para português](#tradução-para-português)
- [Ferramentas](#ferramentas)
- [Recuperar um save corrompido](#recuperar-um-save-corrompido)
- [Rodar sem instalar nada](#rodar-sem-instalar-nada)
- [Usando o bundle .exe do projeto original](#usando-o-bundle-exe-do-projeto-original)
- [Gerar o executável](#gerar-o-executável)
- [Testes](#testes)
- [Estrutura dos arquivos](#estrutura-dos-arquivos)
- [Desinstalar](#desinstalar)

---

## Como funciona

### As duas pastas

O SW Boost é entregue como uma pasta separada só porque precisa vir de algum
lugar. O `instalar.py` copia o que interessa para dentro da pasta do jogo, e
**a pasta do boost pode ser apagada depois**. Daí em diante existe uma pasta
só: a do jogo.

Quem prefere não copiar nada pode rodar de fora, apontando para o jogo:

```bash
python play.py --game-dir /caminho/do/socialwarriors
```

Funciona igual, mas aí você não tem o `jogar.bat` dentro da pasta do jogo
para dar clique duplo.

### O que o boost faz com o servidor

O SW Boost **não altera nenhum arquivo do jogo**. O `play.py` importa o
`server.py` do projeto original, pega o objeto Flask que ele já montou e
troca funções em cima dele em memória.

Consequência prática: apagar os arquivos do boost devolve exatamente o
comportamento de fábrica. Nenhum arquivo do jogo é modificado, e nenhum é
sobrescrito — por isso, dentro da pasta do jogo, o README vira `SWBOOST.md` e
o requirements vira `requirements-swboost.txt` (os dois nomes já existem lá).

---

## Opções do lançador

```
python play.py [opções]
```

| Opção | O que faz |
| --- | --- |
| `--fps N` | 30 (padrão), 60 ou 120 — veja [modo turbo](#modo-turbo-em-detalhe) |
| `--resolucao R` | `janela` (padrão), `1920x1080`, `2560x1440`, `3840x2160`, `original`, ou `LARGURAxALTURA` |
| `--tela-original` | volta ao `play.html` do projeto, travado em 760×600 |
| `--port N` | porta do servidor (padrão 5055) |
| `--host ENDEREÇO` | endereço de escuta (padrão 127.0.0.1) |
| `--browser CAMINHO` | usar um navegador específico, ou `none` |
| `--projector` | abrir com o Flash Player standalone, sem navegador |
| `--no-browser` | só sobe o servidor, não abre nada |
| `--no-quickplay` | abre a tela de login em vez da última vila |
| `--verbose` | mostra o log completo |
| `--check` | diagnostica a instalação e sai |
| `--list-browsers` | lista os Flash encontrados na máquina |
| `--write-config` | cria um `swboost.ini` comentado |
| `--game-dir CAMINHO` | usar o boost sem copiá-lo para a pasta do jogo |
| `--exe` | usar o executável do bundle 0.02a em vez do código-fonte |
| `--server {auto,waitress,flask}` | qual servidor HTTP usar |

---

## Arquivo de configuração

Para não repetir opções toda vez:

```bash
python play.py --write-config
```

Isso cria um `swboost.ini` com todos os valores comentados. A ordem de
precedência é:

```
padrão  <  swboost.ini  <  variáveis SWBOOST_*  <  argumentos da linha de comando
```

Um `.ini` com erro de digitação não derruba o lançador: ele avisa e segue com
os padrões.

---

## Desempenho medido

Comparação feita com `ferramentas/benchmark.py`, servidor original contra
turbinado, na mesma máquina e com os mesmos arquivos.

### Configuração do jogo (`get_game_config.php`)

| | Original | SW Boost |
| --- | --- | --- |
| Transferido | 1,0 MB | **59,6 KB** (gzip) |
| 1ª chamada | 23,1 ms | **5,0 ms** |
| 2ª chamada | 22,2 ms | **1,5 ms** |

O JSON de 1 MB era reserializado a cada carregamento do jogo, e a função
`make_dynamic()` recalculava as datas do minigame de dardos toda vez. Agora é
serializado e comprimido uma vez só.

### Assets (sprites, imagens, sons)

| | Original | SW Boost |
| --- | --- | --- |
| 1ª partida (60 arquivos, 4,9 MB) | 108 ms | **77 ms** |
| 2ª partida | 91 ms, **60 revalidações HTTP** | **0 pedidos** |
| Arquivos com cache longo | 0/60 | **60/60** |

O servidor original não define `Cache-Control`, então o navegador revalida
cada asset a cada partida — centenas de idas e voltas antes do mapa aparecer.

> Os tempos são de `localhost`, onde a rede custa quase nada. Numa máquina
> real com o plugin Flash, o que pesa é a **quantidade** de idas e voltas, e é
> exatamente isso que o cache elimina.

### Outras mudanças

- **waitress** no lugar do servidor de desenvolvimento do Werkzeug
- filtro das linhas repetitivas do console (caro no Windows)
- gravação de save atômica, com backups rotativos

---

## Resolução: Full HD, 2K e 4K

O que prendia o jogo em 760×600 era o `<embed>` do `templates/play.html`. O
jogo em si sempre soube se virar em qualquer tamanho:

| Peça | Como se comporta |
| --- | --- |
| Palco | `scaleMode = NO_SCALE` — área maior mostra **mais mapa**, sem esticar |
| Barra de baixo | ancorada em `stageHeight - 125` |
| Slider de zoom | ancorado em `stageWidth - 24` |
| Caixa de objetivos | ancorada à esquerda |
| Popups e fundo | reposicionados por `onWidescreenChange()` no `Event.RESIZE` |
| Tela cheia | `toggleFullscreen()` embutido, no botão de opções do jogo |

Conferido no papel, reproduzindo o cálculo de `GuiManager.widescreen()`: em
760×600, 1090×600, 1920×1080 e 2560×1440 todos os elementos caem dentro da
tela.

A página nova (`swboost/tela.py`) entrega os **mesmos 16 flashvars e o mesmo
SWF** do `play.html` original — só as dimensões mudam. Isso foi verificado
comparando as duas páginas servidas lado a lado.

**A troca:** mais mapa visível significa mais unidades desenhadas por quadro.
Numa batalha grande em 4K o desempenho cai. Use uma resolução menor ou
"Preencher a janela" se isso incomodar.

Para voltar ao comportamento antigo: `--tela-original`.

---

## Modo turbo em detalhe

```bash
python play.py --fps 60     # 2x
python play.py --fps 120    # 4x
```

**A taxa de quadros no Social Wars controla a velocidade do jogo, não a
suavidade.** A lógica conta quadros, não tempo real.

| Sistema | A 60 fps |
| --- | --- |
| Construção, colheita, produção | **inalterado** (tempo real do servidor) |
| Fila de treino de unidades | **inalterado** |
| Movimento e animação das unidades | **2x mais rápido** |
| Cadência de ataque e IA | **2x mais rápida** |
| Rolagem do mapa pelo teclado | **2x mais rápida** |

O combate continua equilibrado porque os dois lados aceleram junto, mas a
sensação do jogo muda bastante.

Nenhum arquivo é modificado: a troca acontece em memória, e cada taxa tem sua
própria entrada no cache do navegador. Para voltar ao normal, rode sem
`--fps`.

A explicação com o código descompilado que comprova está na
[análise técnica](ANALISE_TECNICA.md#1-a-pergunta-dos-60120-hz--resposta-honesta).

---

## Tradução para português

O jogo já foi feito para isso: `core/Language.as` declara
`LANGUAGE_BRASILIAN = "br"`. E os nomes de construções, unidades e objetivos
vêm do servidor, não do SWF — então dá para traduzi-los **sem tocar em nenhum
arquivo Flash**, usando o sistema de mods que o projeto já tem.

```bash
python ferramentas/gerar_mod_traducao.py --ativar
```

Gera `mods/ptbr.json` com ~1.100 textos, já traduzindo os termos mais comuns,
e ativa o mod no `mods.txt`.

Pontos importantes:

- O que o dicionário não cobre continua em inglês. Edite o JSON aos poucos.
- **Rodar de novo preserva tudo o que você já traduziu à mão.**
- Deixe a linha `ptbr` **antes** de mods que acrescentem ou removam itens no
  `mods.txt` (os caminhos do jsonpatch são por índice).

Os textos da interface que estão dentro do SWF são um problema separado e bem
mais trabalhoso — veja
[IDEIAS.md](IDEIAS.md#1-tradução-para-português).

---

## Ferramentas

```bash
# Medir o desempenho do servidor
python ferramentas/benchmark.py
python ferramentas/benchmark.py --url http://127.0.0.1:5056   # comparar com outro

# Ver / gravar / desfazer a taxa de quadros direto nos arquivos SWF
python ferramentas/swf_framerate.py info    assets/flash/SWLoader.swf
python ferramentas/swf_framerate.py set 60  assets/flash/SWLoader.swf
python ferramentas/swf_framerate.py restore assets/flash/SWLoader.swf

# Gerar o mod de tradução
python ferramentas/gerar_mod_traducao.py --ativar
```

O `swf_framerate set` sempre cria um backup `.orig`, e o `restore` devolve o
arquivo byte a byte. Use só se você precisa da mudança gravada em disco —
para jogar, `play.py --fps 60` é melhor, porque não toca em nada.

---

## Recuperar um save corrompido

O SW Boost guarda cópias automáticas em **`save_backups/`** (fora de
`saves/`, porque o carregador do jogo tenta abrir como JSON tudo o que
estiver dentro de `saves/`, inclusive pastas, e quebra).

Para voltar à cópia mais recente:

```bash
python -c "import sys; sys.path.insert(0,'.'); from swboost.saves import restore_latest_backup; print(restore_latest_backup('saves', 'SEU-USERID'))"
```

O `USERID` é o nome do arquivo em `saves/` sem o `.save.json`.

---

## Rodar sem instalar nada

### Sem instalar dependências no sistema

O `jogar.bat` e o `jogar.sh` criam um ambiente virtual (`.venv`) dentro da
pasta do jogo. Nada é gravado fora dali e o Windows não pede elevação. Se o
`.venv` não puder ser criado, eles caem para `pip install --user`.

### Sem navegador — modo projector

```bash
python play.py --projector
```

O Flash Player standalone (*projector*) abre o jogo direto, sem navegador.
Sem `<embed>` não existem flashvars, então os 17 parâmetros que o `play.html`
passaria vão na query string do SWF — que é de onde o jogo lê, via
`stage.loaderInfo.parameters`.

Onde procurar um projector, em ordem:

1. `C:\Windows\SysWOW64\Macromed\Flash\FlashPlayerApp.exe` — quem já teve
   Flash instalado costuma ter, e é um projector completo
2. uma pasta `browser/` dentro da pasta do jogo, onde você pode largar
   qualquer navegador ou projector portátil
3. instalação normal do Flash Player

O `play.py --list-browsers` mostra o que foi encontrado.

> **Aviso honesto:** a URL do modo projector está testada (o SWF é servido
> corretamente com todos os parâmetros), mas **não foi possível abrir o Flash
> de fato** para confirmar — o ambiente onde isto foi desenvolvido é Linux sem
> Flash Player.

---

## Usando o bundle .exe do projeto original

O executável da release 0.02a tem o servidor Python congelado dentro, então
as melhorias de servidor não se aplicam. A parte de inicialização funciona:

```bash
python play.py --exe
```

Sobe o executável, espera responder e abre o Flash. Para ter os ganhos de
desempenho, rode a partir do código-fonte.

---

## Gerar o executável

```bash
pip install pyinstaller
python build_exe/construir.py              # arquivo único (padrão)
python build_exe/construir.py --onedir     # pasta (melhor com AppLocker)
```

O executável **não empacota os assets do jogo** (~1,4 GB): ele é só o
lançador e roda contra a pasta onde estiver. Resultado: ~13 MB.

Ele não pede administrador — o PyInstaller só embute o manifesto de elevação
quando `uac_admin=True`, e isso fica explicitamente desligado.

O PyInstaller não faz compilação cruzada: um `.exe` de Windows só pode ser
gerado no Windows. Sem um Windows à mão, use o workflow
`.github/workflows/build-windows.yml` (aba **Actions** do repositório), que
também verifica a cada build que o binário não pede administrador.

---

## Testes

```bash
python -m unittest discover -s tests -v
```

76 testes, sem dependência dos arquivos do jogo. Cobrem a leitura e reescrita
de SWF, o cache de taxa de quadros, o ajuste do `<embed>`, a configuração, o
filtro de console, a gravação atômica de saves, o gerador de tradução, a URL
do modo projector e os caminhos de um build congelado.

---

## Estrutura dos arquivos

```
play.py                  lançador — é por aqui que se começa
preparar.py              instala tudo do zero, em um comando
PREPARAR.bat             o mesmo, com clique duplo (Windows)
instalar.py              copia o boost para a pasta do jogo
jogar.bat / jogar.sh     atalhos de um clique
swboost/
  boost.py               carrega o server.py do jogo e aplica tudo
  web.py                 cache de assets, gzip, entrada rápida, projector
  swf.py                 leitura e reescrita do cabeçalho SWF
  saves.py               gravação atômica e backups
  browsers.py            detecção de navegador e projector com Flash
  tela.py                página do jogo em Full HD / 2K / 4K
  gamedir.py             achar a pasta do jogo (sem dependências)
  console.py             filtro do log
  settings.py            swboost.ini, variáveis de ambiente, argumentos
build_exe/
  construir.py           gera o SocialWars.exe (PyInstaller)
.github/workflows/
  build-windows.yml      gera o .exe do Windows na nuvem
ferramentas/
  benchmark.py           mede o servidor
  swf_framerate.py       taxa de quadros em disco
  gerar_mod_traducao.py  esqueleto de tradução PT-BR
tests/                   testes automatizados
```

---

## Desinstalar

Apague, de dentro da pasta do jogo: `play.py`, `jogar.bat`, `jogar.sh`,
`SocialWars.exe`, `.venv/`, `swboost/`, `ferramentas/`,
`requirements-swboost.txt`, `SWBOOST.md`, `ANALISE_TECNICA.md`, `IDEIAS.md`,
`MANUAL.md`, `swboost.ini` e `boost_cache/`.

O jogo volta ao original — nenhum arquivo dele foi tocado nem sobrescrito.
Seus saves e os backups em `save_backups/` continuam onde estão.

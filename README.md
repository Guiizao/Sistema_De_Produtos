# SW Boost — Social Wars com um clique

Camada de melhorias para o projeto de preservação
[AcidCaos/socialwarriors](https://github.com/AcidCaos/socialwarriors).

Resolve três coisas:

1. **Iniciar ficou simples.** Um comando (ou um clique duplo) sobe o
   servidor, acha o navegador com Flash e já entra na sua vila.
2. **O carregamento ficou mais rápido.** Cache de assets, compressão e um
   servidor HTTP de verdade.
3. **Seu save parou de correr risco.** Gravação atômica e backups
   automáticos.

E responde a pergunta dos 60 Hz — com um teste, e com a resposta honesta:
👉 [`ANALISE_TECNICA.md`](ANALISE_TECNICA.md)

> **Nada do jogo original é alterado.** O SW Boost importa o `server.py`,
> pega o Flask já montado e troca funções em cima dele. Apagar estes
> arquivos devolve o comportamento de fábrica.

---

## Sem permissão de administrador?

Se a máquina é do trabalho/escola e você não consegue instalar nada, dá para
jogar assim mesmo. São dois problemas separados, com soluções separadas.

### Problema 1 — "pede administrador para iniciar"

Isso **não vem do jogo nem do executável**. Vem do `pip install` tentando
gravar no Python do sistema (que fica em `Arquivos de Programas`).

Já está resolvido: o `jogar.bat` cria um ambiente virtual (`.venv`) dentro da
própria pasta do jogo e instala tudo lá. Nada é gravado fora da pasta e o
Windows não pede elevação nenhuma.

> Só cuide de **não** deixar a pasta do jogo dentro de `Arquivos de
> Programas` — ali o Windows bloqueia a gravação dos saves. Área de Trabalho,
> Documentos, Downloads ou um pendrive funcionam.

### Problema 2 — "não consigo nem instalar o Python"

Use o executável: leva o Python inteiro dentro dele.

1. Aba **Actions** deste repositório → **Build Windows executable** → **Run workflow**
2. Quando terminar, baixe o artefato **SocialWars-windows**
3. Descompacte e ponha o `SocialWars.exe` dentro da pasta do jogo
4. Clique duas vezes

São ~15 MB (os assets do jogo continuam na pasta, não vão para dentro do
exe). O executável **não pede administrador** — o build nem embute o
manifesto que pediria, e o próprio workflow verifica isso a cada build.

> Por que o workflow e não um exe pronto aqui? Porque o PyInstaller não faz
> compilação cruzada: um `.exe` de Windows só pode ser gerado no Windows. O
> workflow usa uma máquina Windows do GitHub para isso — de graça, e sem
> precisar de permissão na sua.

Se você tem Python e quer gerar o executável você mesmo:

```bash
pip install pyinstaller
python build_exe/construir.py
```

### Problema 3 — "não consigo baixar/instalar um navegador Flash"

Aí entra o **Flash Player standalone** (o *projector*): é um único
executável, não instala nada, não pede administrador — e abre o jogo **sem
navegador nenhum**.

```bash
python play.py --projector
```

Antes de sair procurando para baixar, veja se ele **já está na sua máquina**.
Quem já teve Flash instalado costuma ter isto aqui:

```
C:\Windows\SysWOW64\Macromed\Flash\FlashPlayerApp.exe
```

Esse arquivo é um projector completo. O lançador procura por ele sozinho:

```bash
python play.py --list-browsers
python play.py --check
```

Se achar, ele já usa. Se você conseguir o executável do projector de outra
forma (baixar em casa e trazer num pendrive, por exemplo), é só largá-lo numa
pasta `browser/` dentro da pasta do jogo — o lançador encontra.

> **Aviso honesto:** o modo projector foi construído a partir do código
> descompilado do jogo (ele lê os parâmetros de `loaderInfo.parameters`, que
> no projector vêm da query string) e a URL gerada está testada — o SWF é
> servido corretamente com todos os 17 parâmetros. Mas **não pude abrir o
> Flash de verdade** para confirmar, porque o ambiente onde isto foi
> desenvolvido é Linux sem Flash Player. Se não funcionar de primeira, me
> diga o que apareceu.

---

## Instalação

Você precisa da **versão em código-fonte** do jogo (a branch `main` do
repositório original — a que tem `server.py`). O bundle `.exe` da release
0.02a funciona só para a parte de inicialização; veja
[Usando o bundle .exe](#usando-o-bundle-exe).

```bash
# 1. Pegue o jogo (uma vez só — são ~1,4 GB de assets)
git clone https://github.com/AcidCaos/socialwarriors.git

# 2. Copie o SW Boost para dentro da pasta do jogo
python instalar.py socialwarriors
```

## Como jogar

Dentro da pasta do jogo:

| Sistema | Comando |
| --- | --- |
| Windows | clique duplo em **`jogar.bat`** |
| Windows, sem Python | clique duplo em **`SocialWars.exe`** ([como obter](#problema-2--não-consigo-nem-instalar-o-python)) |
| GNU/Linux | **`./jogar.sh`** |

Na primeira execução as dependências são instaladas sozinhas, num ambiente
virtual dentro da própria pasta — **sem pedir administrador**. Depois disso o
servidor sobe, o Flash abre e você cai direto na sua vila.

Antes: rodar o executável, abrir um navegador Flash à parte, digitar
`http://127.0.0.1:5055/`, escolher a vila na tela de login.
Agora: um clique.

### Não achou o navegador?

O jogo precisa de Flash. Instale o
[FlashBrowser](https://github.com/radubirsan/FlashBrowser/releases/latest)
(recomendado) ou veja as alternativas no `FLASH.md` do projeto original.

Se você usa uma versão **portátil**, é só colocá-la em uma pasta `browser/`
dentro da pasta do jogo — o lançador encontra sozinho.

Para conferir o que foi detectado:

```bash
python play.py --list-browsers
python play.py --check          # diagnóstico completo da instalação
```

---

## O que melhorou

Medido com `ferramentas/benchmark.py`, original contra turbinado, mesma
máquina. (Detalhes e método em [`ANALISE_TECNICA.md`](ANALISE_TECNICA.md).)

| | Original | SW Boost |
| --- | --- | --- |
| Configuração do jogo, transferida | 1,0 MB | **59,6 KB** |
| Configuração do jogo, 2ª chamada | 22,2 ms | **1,5 ms** |
| Assets na 2ª partida | 60 revalidações HTTP | **0 pedidos** |
| Servidor HTTP | Werkzeug (desenvolvimento) | **waitress** (multi-thread) |
| Gravação de save | trunca antes de escrever | **atômica + backups** |
| Entrar no jogo | servidor → navegador → login | **um clique** |

Também corrigido: o `requirements.txt` original não lista `requests` nem
`jsonpatch`, então uma instalação limpa quebrava no import.

---

## Modo turbo (60 / 120 fps)

```bash
python play.py --fps 60
```

**Leia isto antes de usar.** No Social Wars a taxa de quadros **não** é só
suavidade: a lógica do jogo conta quadros, não tempo. A 60 fps as unidades
andam, atacam e animam **duas vezes mais rápido**. A 120 fps, quatro.

O que **não** muda: construção, colheita, produção e filas de treino — tudo
isso é calculado por tempo real no servidor.

Ou seja: é um **modo turbo**, não um ganho de qualidade. Divertido de
experimentar, desligado por padrão. A explicação completa, com o código do
jogo que comprova, está em [`ANALISE_TECNICA.md`](ANALISE_TECNICA.md#1-a-pergunta-dos-60120-hz--resposta-honesta).

Nenhum arquivo é modificado: a troca acontece em memória, e cada taxa tem sua
própria entrada no cache do navegador. Voltar ao normal é rodar `play.py` sem
`--fps`.

---

## Opções

```
python play.py [opções]

  --fps N            30 (padrão) | 60 | 120 — veja o aviso acima
  --port N           porta do servidor (padrão 5055)
  --browser CAMINHO  navegador específico, ou 'none'
  --no-browser       só sobe o servidor
  --no-quickplay     abre a tela de login em vez da última vila
  --projector        abre com o Flash Player standalone, sem navegador
  --verbose          mostra o log completo
  --check            diagnostica a instalação e sai
  --list-browsers    lista os navegadores com Flash encontrados
  --write-config     cria um swboost.ini comentado
  --game-dir CAMINHO usar o boost sem copiá-lo para a pasta do jogo
```

Para deixar as escolhas fixas, gere o arquivo de configuração:

```bash
python play.py --write-config    # cria swboost.ini, todo comentado
```

---

## Traduzir o jogo para português

O jogo já foi feito para isso: `core/Language.as` declara
`LANGUAGE_BRASILIAN = "br"`. E os nomes de construções, unidades e objetivos
vêm do servidor, não do SWF — então dá para traduzi-los sem tocar em nenhum
arquivo Flash, usando o sistema de mods que o projeto já tem.

```bash
python ferramentas/gerar_mod_traducao.py --ativar
```

Gera `mods/ptbr.json` com ~1.100 textos, já traduzindo os termos mais comuns
("Wood Factory I" → "Fábrica de Madeira I"), e ativa o mod. O que o
dicionário não cobre continua em inglês — é só editar o JSON aos poucos.
**Rodar de novo preserva tudo o que você já traduziu à mão.**

Os textos da interface que estão dentro do SWF são um problema separado, com
solução mais trabalhosa — veja [`IDEIAS.md`](IDEIAS.md#1-tradução-para-português-).

---

## Ferramentas

```bash
# Comparar o desempenho do servidor
python ferramentas/benchmark.py

# Ver / gravar / desfazer a taxa de quadros direto nos arquivos SWF
python ferramentas/swf_framerate.py info    assets/flash/SWLoader.swf
python ferramentas/swf_framerate.py set 60  assets/flash/SWLoader.swf
python ferramentas/swf_framerate.py restore assets/flash/SWLoader.swf

# Gerar um mod de tradução para português
python ferramentas/gerar_mod_traducao.py --ativar
```

O `set` sempre cria um backup `.orig`, e o `restore` devolve o arquivo byte a
byte. Use isto só se você precisa da mudança gravada em disco — para jogar,
`play.py --fps 60` é melhor, porque não toca em nada.

---

## Recuperar um save corrompido

O SW Boost mantém cópias em **`save_backups/`** (fora de `saves/` — o
carregador do jogo tenta abrir como JSON tudo o que estiver dentro de
`saves/`, inclusive pastas, e quebra). Para voltar à mais recente:

```python
python -c "import sys; sys.path.insert(0,'.'); from swboost.saves import restore_latest_backup; print(restore_latest_backup('saves', 'SEU-USERID'))"
```

O `USERID` é o nome do arquivo em `saves/` sem o `.save.json`.

---

## Usando o bundle .exe

O executável da release 0.02a tem o servidor Python congelado dentro, então
as melhorias de servidor não se aplicam. A parte de inicialização funciona:

```bash
python play.py --exe
```

Sobe o executável, espera ele responder e abre o navegador com Flash.

Para ter os ganhos de desempenho, rode a partir do código-fonte.

---

## Testes

```bash
python -m unittest discover -s tests -v
```

52 testes, sem dependência dos arquivos do jogo: cobrem a leitura e reescrita
de SWF, o cache de taxa de quadros, o ajuste do `<embed>`, a configuração, o
filtro de console e a gravação atômica de saves.

---

## Estrutura

```
play.py                  lançador — é por aqui que se começa
instalar.py              copia o boost para a pasta do jogo
jogar.bat / jogar.sh     atalhos de um clique
swboost/
  boost.py               carrega o server.py do jogo e aplica tudo
  web.py                 cache de assets, gzip, entrada rápida, /play.html
  swf.py                 leitura e reescrita do cabeçalho SWF
  saves.py               gravação atômica e backups
  browsers.py            detecção de navegador com Flash
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

Apague `play.py`, `jogar.bat`, `jogar.sh`, `SocialWars.exe`, `.venv/`,
`swboost/`, `ferramentas/`, `requirements-swboost.txt`,
`SWBOOST.md`, `ANALISE_TECNICA.md`, `IDEIAS.md`, `swboost.ini` e
`boost_cache/`. O jogo volta ao original — nenhum arquivo dele foi tocado
nem sobrescrito (dentro da pasta do jogo este README se chama `SWBOOST.md`,
justamente para não passar por cima do README do projeto). Seus saves e os
backups em `save_backups/` continuam onde estão.

---

## Licença e créditos

O jogo e o servidor de preservação são do
[projeto Social Warriors](https://github.com/AcidCaos/socialwarriors),
sob **GPL v3**. Este material é uma camada de melhorias construída em cima
dele e segue a mesma licença.

*Social Wars* é uma obra da Social Point. Este é um projeto de preservação
sem fins lucrativos.

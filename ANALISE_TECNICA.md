# Análise técnica — Social Wars (preservação AcidCaos/socialwarriors)

Documento de apoio ao **SW Boost**. Registra o que foi investigado, como, e
por que cada decisão foi tomada.

**Método:** o SWF principal do jogo (`assets/flash/Basesec_1.5.4.swf`, 6 MB
descompactado) foi descompilado com o JPEXS Free Flash Decompiler (1.387
classes ActionScript 3). O servidor Python foi lido e medido em execução,
comparando a versão original com a turbinada lado a lado.

---

## 1. A pergunta dos 60/120 Hz — resposta honesta

**Resumo: subir a taxa de quadros no Social Wars não deixa o jogo mais suave.
Deixa o jogo mais rápido.** 60 fps = tudo em velocidade 2x. 120 fps = 4x.

Isso não é um palpite. Está no código.

### O que foi encontrado

O SWF declara 30 fps no cabeçalho:

```
SWLoader.swf        SWF v10 (zlib), palco 760x600,  30 fps, 1 frame
Basesec_1.5.4.swf   SWF v10 (zlib), palco 1400x600, 30 fps, 1 frame
```

`frameCount = 1` já é o primeiro indício: não existe animação de linha do
tempo no filme principal, tudo é feito por código. A classe do documento é
`core.Base`, e o laço principal do jogo está preso ao evento de quadro:

```actionscript
// core/Base.as
this.addEventListener(Event.ENTER_FRAME, this.UpdateGame);
```

E o `UpdateGame` conta **quadros**, não tempo:

```actionscript
private function UpdateGame(... rest) : void
{
   ++this.numIteraciones;
   ...
   if(this.numIteraciones % 30 == 0)        // "passou 1 segundo"
   {
      this.updateEverySecond();
   }
   if(this.numIteraciones % (30 * 60) == 0) // "passou 1 minuto"
   {
      this.updateEveryMinute();
   }
   Base.Iso.Update();
}
```

O número 30 está escrito no código como sinônimo de "um segundo". O motor
isométrico faz o mesmo, com o próprio contador de quadros:

```actionscript
// core/isoengine/IsoEngine.as
public function Update() : void
{
   for each(_loc2_ in _loc1_) { _loc2_.Update(this.uiGameFrame); }
   if(this.uiGameFrame % 70 == 0 ...) { this.amOverattacked(); }
   if(this.uiGameFrame % 85 == 0)     { ...bboxPlayers... }
   ++this.uiGameFrame;
}
```

E cada unidade decide o que fazer a partir do número do quadro — inclusive a
cadência de ataque:

```actionscript
// core/isoengine/IsoUnit.as
override public function Update(param1:uint) : void
{
   var _loc2_:* = param1 % 61 == 0;              // IA
   var _loc3_:* = (param1 + iDelayAttack) % 5 == 0;  // ataque
   var _loc4_:* = param1 % 2 == 0;               // direção do sprite
   ...
   if(this.bAttacking && _loc3_ ...) { this.updateAttack(param1); }
   this.updateMove();
   if(_loc4_) { this.updateDirection(); }
}
```

Nenhuma dessas contas usa *delta time*. Não existe `getTimer()` medindo o
intervalo entre quadros e escalando o movimento. O único `getTimer()` do
`Base.as` serve para sincronizar o relógio com o servidor, e o único lugar em
todo o jogo que escreve em `stage.frameRate` é o medidor de FPS de depuração
(`core/Stats.as`) — ou seja, **o valor do cabeçalho do SWF é quem manda.**

A rolagem do mapa pelo teclado também é por quadro (`moveMap(50, 0)` a cada
quadro): a 60 fps o mapa anda duas vezes mais rápido.

### O que NÃO muda com a taxa de quadros

A economia do jogo é calculada com carimbos de tempo reais no servidor
Python (`engine.timestamp_now()`), e os temporizadores de longa duração usam
`flash.utils.Timer` em milissegundos. Então:

| Sistema | A 60 fps |
| --- | --- |
| Construção, colheita, produção de recursos | **inalterado** (tempo real do servidor) |
| Fila de treino de unidades | **inalterado** |
| Movimento e animação das unidades | **2x mais rápido** |
| Cadência de ataque e IA de combate | **2x mais rápida** |
| Rolagem do mapa pelo teclado | **2x mais rápida** |
| Partículas, efeitos, tweens | **2x mais rápidos** |

Combate continua "justo" porque os dois lados aceleram junto — mas a
sensação do jogo muda, e é uma mudança grande.

### O que isso significa na prática

O modo turbo (`--fps 60`) é **oferecido, testado e desligado por padrão**. É
uma opção legítima para quem quer as batalhas e o vaivém das unidades mais
ágeis; não é um ganho de suavidade. A 30 fps o jogo já roda na velocidade
para a qual foi balanceado.

### O que seria preciso para 60 fps *de verdade*

Suavidade real a 60 fps exigiria alterar o ActionScript do jogo, não o
cabeçalho:

1. rodar o `ENTER_FRAME` a 60 Hz mas executar a lógica só em quadros pares
   (mantendo 30 Hz de simulação, com 60 Hz de renderização);
2. desacoplar as animações de linha do tempo dos sprites, que hoje avançam na
   taxa do palco — seriam ~860 SWF de sprites a ajustar;
3. interpolar a posição das unidades entre dois passos de simulação, senão o
   movimento continua com a granularidade de 30 Hz.

É um projeto de reescrita do motor, com risco alto de quebrar o
balanceamento e as quests. Ficou fora deste trabalho de propósito, e está
registrado em `IDEIAS.md` como caminho futuro.

---

## 2. Qualidade de renderização: o jogo se auto-limita

O `templates/play.html` pede `quality=high` no `<embed>`, mas o jogo
sobrescreve isso ao iniciar:

```actionscript
// core/Base.as, ao entrar no mapa
this.getStage().quality = "medium";
this.getStage().scaleMode = StageScaleMode.NO_SCALE;
this.getStage().align = StageAlign.TOP_LEFT;
```

E reafirma o valor durante a interação com o mapa:

```actionscript
if(this.getStage() != null && this.getStage().quality != "MEDIUM")
{
   this.getStage().quality = "MEDIUM";
}
```

**Consequência:** mexer no `quality` do HTML não adianta — o jogo devolve
para `medium` sozinho. Foi uma decisão do estúdio para segurar o desempenho
em máquinas de 2012. Mudar isso exigiria alterar o ActionScript.

**Efeito colateral bom:** como o palco é `NO_SCALE`, aumentar o `<embed>`
**não** escala a imagem — mostra *mais mapa*. Não custa desempenho e não
borra nada. Por isso `embed_width` existe como opção no `swboost.ini`.

---

## 3. Desempenho do servidor — onde estava o custo

Medições com `ferramentas/benchmark.py`, servidor original (porta 5056)
contra turbinado (porta 5055), mesma máquina, mesmos arquivos.

### Configuração do jogo (`get_game_config.php`)

| | Original | SW Boost |
| --- | --- | --- |
| Transferido | 1,0 MB | **59,6 KB** (gzip) |
| 1ª chamada | 23,1 ms | **5,0 ms** |
| 2ª chamada | 22,2 ms | **1,5 ms** |

Três problemas somados:

1. **Sem compressão.** É um JSON de 1 MB com 900 itens de catálogo. Comprime
   para 6% do tamanho.
2. **Sem cache.** `get_game_config()` chama `make_dynamic()` a cada pedido,
   que recalcula as datas do minigame de dardos com `strptime`/`mktime` em
   laço, e o Flask re-serializa o dicionário inteiro toda vez.
3. **JSON expandido.** O `config/main.json` está indentado: 1,65 MB em disco
   para 1,09 MB de conteúdo real.

O boost serializa uma vez, comprime uma vez e reaproveita por 5 minutos
(configurável). As datas dos dardos mudam por semana; 5 minutos é folgado.

### Assets (sprites, imagens, sons)

| | Original | SW Boost |
| --- | --- | --- |
| 1ª partida (60 arquivos, 4,9 MB) | 108 ms | **77 ms** |
| 2ª partida | 91 ms, **60 revalidações HTTP 304** | **0 pedidos** |
| Arquivos com cache de longa duração | 0/60 | **60/60** |

O `send_from_directory` do jogo não define `Cache-Control`. O navegador até
guarda o arquivo, mas **revalida cada um** a cada partida. São centenas de
idas e voltas ao servidor antes do mapa aparecer. Com
`Cache-Control: public, max-age=1 ano, immutable`, a segunda partida não faz
pedido nenhum — os assets do jogo nunca mudam em disco.

> Os tempos acima são de `localhost`, onde a rede custa quase nada. Numa
> máquina real, com o plugin Flash e milhares de arquivos, o que pesa é a
> quantidade de idas e voltas, não os bytes — e é exatamente isso que o
> cache elimina.

### Servidor HTTP

O `server.py` sobe com `app.run()`, o servidor de desenvolvimento do
Werkzeug — que o próprio Flask avisa não ser para uso real. O boost usa
**waitress** (multi-thread, mantém a conexão viva), com queda automática
para o servidor do Flask se o waitress não estiver instalado.

### Log do console

O servidor imprime uma linha por comando do jogo, por config carregada e por
save gravado. Uma partida gera milhares de linhas. No Windows, escrever no
console é uma chamada de sistema síncrona e cara. O boost filtra apenas as
linhas repetitivas conhecidas (`--verbose` desliga o filtro).

---

## 4. Defeitos encontrados no projeto original

### 4.1 `requirements.txt` incompleto (impede instalação limpa)

O arquivo lista só `flask`. Mas:

- `server.py` faz `import requests` no topo;
- `get_game_config.py` faz `import jsonpatch`.

Numa máquina limpa, `pip install -r requirements.txt` seguido de
`python server.py` falha no import. O `requirements.txt` deste repositório
corrige a lista. Além disso, o `requests` só seria usado dentro de um bloco
`if False:` (a variante que baixaria os assets do GitHub), então o boost
instala um substituto inofensivo quando a biblioteca falta — e que levanta
erro claro se algum dia for realmente usada.

### 4.2 Gravação de save não atômica (risco de perder a vila)

```python
# sessions.py, original
def save_session(USERID: str):
    file = f"{USERID}.save.json"
    village = session(USERID)
    with open(os.path.join(SAVES_DIR, file), 'w') as f:
        json.dump(village, f, indent=4)
```

Abrir em `'w'` **trunca o arquivo imediatamente**. O JSON é escrito depois.
Se o processo morrer nesse intervalo — fechar a janela, queda de energia,
matar o servidor — o save fica cortado pela metade. E o carregamento
simplesmente desiste dele:

```python
except json.decoder.JSONDecodeError as e:
    print("Corrupted JSON.")
    continue
```

A vila some da tela de login sem nenhum aviso. E `save_session()` é chamado
a cada lote de comandos, ou seja, o tempo todo.

O boost grava num arquivo temporário, faz `fsync` e só então `os.replace()`
(atômico no Windows e no Linux), além de manter backups rotativos em
`saves/backups/`. Funções auxiliares `backup_session()` existem no original
mas estão vazias, com um `# TODO`.

### 4.3 `load_saves()` explode com qualquer coisa que não seja um save

```python
for file in os.listdir(SAVES_DIR):
    try:
        save = json.load(open(os.path.join(SAVES_DIR, file)))
    except json.decoder.JSONDecodeError as e:
        print("Corrupted JSON.")
        continue
```

A pasta é percorrida inteira e **toda** entrada é aberta como JSON, sem
verificar se é sequer um arquivo. Uma subpasta em `saves/` levanta
`IsADirectoryError`, que não é capturado — e como `load_saves()` roda durante
o `import server`, o servidor nem chega a subir. O mesmo vale para um
`.txt`, um `.zip` de backup ou um `Thumbs.db`.

Isto foi descoberto na prática: a primeira versão deste trabalho guardava os
backups em `saves/backups/` e derrubou o servidor na inicialização. Duas
consequências para o SW Boost:

- os backups ficam em **`save_backups/`**, irmã de `saves/`, nunca dentro;
- antes de importar o `server.py`, o boost verifica a pasta e avisa em bom
  português o que precisa ser movido — já que depois do import é tarde.

O `play.py --check` faz a mesma verificação.

---

## 5. Recursos escondidos no jogo

Encontrados na descompilação — fazem parte do jogo original, não são
acréscimos:

### Painel de administração

`core/Key.as` guarda uma sequência de teclas ofuscada:

```actionscript
private static var arDebug:Array = [83,68,88,74,90,83,97,99,95,92];
...
var _loc2_:Number = (param1.keyCode + iDB * 3) % 255;
if(_loc2_ == arDebug[iDB]) { ++iDB; }
...
if(iDB == arDebug.length) { Base.Main.bAllowAdminPanel = true; }
```

Desfazendo a ofuscação (`arDebug[i] - 3*i`), a sequência é **SARANDONGA**.
Digitar isso durante a partida libera o painel com comandos como `give`
(recursos), `ff` (avançar o tempo), `spawn`, `loadMap`, `tutorial`, além de
botões para abrir qualquer uma das quests.

### Dois ovos de páscoa

- **Konami Code** (↑↑↓↓←→←→ B A) → "Speech bubbles enabled!"
- **A B A C A B B** → "Blood mode enabled!"

---

## 6. O que o SW Boost deliberadamente **não** faz

- Não altera nenhum arquivo do projeto original. O `play.py` importa o
  `server.py`, pega o objeto Flask pronto e troca funções em cima dele.
  Apagar os arquivos do boost devolve o comportamento de fábrica.
- Não modifica os SWF em disco. A troca de taxa de quadros acontece em
  memória, com cache em `boost_cache/`. (A ferramenta
  `ferramentas/swf_framerate.py` grava em disco para quem quiser, sempre com
  backup `.orig`.)
- Não mexe no balanceamento, nos itens nem nas quests.
- Não sobe a taxa de quadros por conta própria: o padrão é 30 fps.

## 7. O que não foi possível verificar aqui

Este trabalho foi feito em um ambiente Linux sem Flash Player. Foram testados
de ponta a ponta: o servidor, o cache, a compressão, a reescrita de SWF (ida
e volta byte a byte), a gravação de saves, o fluxo de entrada rápida e o
lançador. **Não** foi possível abrir o jogo de fato para confirmar
visualmente o comportamento a 60/120 fps, nem a detecção de navegadores no
Windows (o código cobre os caminhos documentados no `FLASH.md` do projeto).

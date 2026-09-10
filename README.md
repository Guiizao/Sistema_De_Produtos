# Social Wars — jogar com um clique

Deixa o [Social Wars](https://github.com/AcidCaos/socialwarriors) mais fácil
de abrir e mais rápido de carregar. Em vez de ligar o servidor, abrir um
navegador Flash à parte e digitar um endereço, você dá um clique e cai na sua
vila.

Não altera nenhum arquivo do jogo.

---

## Começando

Você lida com **duas pastas**, mas só uma sobra no fim:

- a pasta do **jogo** — é onde tudo acaba morando
- a pasta do **SW Boost** — é só o pacote de instalação, e pode ser apagada depois

As duas ficam **lado a lado**, não uma dentro da outra:

```
ANTES                              DEPOIS
Videos\                            Videos\
├── socialwarriors\                └── socialwarriors\   ← só esta importa
│   ├── server.py                      ├── server.py
│   └── assets\                        ├── assets\
│                                      ├── jogar.bat      ← novo
└── sw-boost\                          ├── play.py        ← novo
    ├── instalar.py                    └── swboost\       ← novo
    └── play.py

                                   (a sw-boost pode ser apagada)
```

### 1. Baixe o jogo

Em qualquer lugar onde você possa gravar — `Videos`, `Documentos`, a Área de
Trabalho. **Menos** dentro de *Arquivos de Programas*.

```bash
git clone https://github.com/AcidCaos/socialwarriors.git
```

São ~1,4 GB e demora. Só precisa fazer isso uma vez.

### 2. Baixe o SW Boost

Ao lado do jogo, na mesma pasta-mãe:

```bash
git clone -b claude/flash-game-startup-perf-njbjww https://github.com/Guiizao/Sistema_De_Produtos.git sw-boost
```

> Sem git? Use o botão verde **Code → Download ZIP** aqui no GitHub e extraia
> para uma pasta chamada `sw-boost`.

### 3. Instale

```bash
cd sw-boost
python instalar.py
```

Ele pergunta onde está o jogo. **Arraste a pasta do jogo para a janela do
terminal** e aperte Enter — o caminho aparece sozinho.

Se preferir digitar de uma vez:

```bash
python instalar.py ..\socialwarriors
```

### 4. Jogue

Entre na pasta do **jogo** (a `sw-boost` já cumpriu o papel e pode ser
apagada):

| Seu caso | O que fazer |
| --- | --- |
| Windows, com Python | clique duplo em **`jogar.bat`** |
| Windows, sem Python | clique duplo em **`SocialWars.exe`** ([como conseguir](#não-tenho-python-e-não-consigo-instalar)) |
| GNU/Linux | **`./jogar.sh`** |

Ou, no terminal: `python play.py`

Na primeira vez ele prepara tudo sozinho (leva um ou dois minutos). Depois é
instantâneo: o servidor sobe, o Flash abre e o jogo começa.

> ⚠️ Não deixe a pasta do jogo dentro de **Arquivos de Programas**. Ali o
> Windows bloqueia a gravação dos saves.

---

## Não abriu?

Rode isto primeiro — ele checa tudo e diz o que está faltando:

```bash
python play.py --check
```

> Se você usa o executável, é `SocialWars.exe --check` (abra o Prompt de
> Comando na pasta do jogo, ou arraste o `SocialWars.exe` para dentro dele e
> digite ` --check` no fim da linha).

Depois ache o seu caso abaixo.

### "Pede administrador"

Não é o jogo. É o `pip` tentando instalar no Python do sistema.

**Já está resolvido**: o `jogar.bat` instala tudo num `.venv` dentro da pasta
do jogo. Se ainda aparecer o pedido, confirme que você não está com a pasta
dentro de *Arquivos de Programas*.

### "Não tenho Python e não consigo instalar"

Use o executável — ele leva o Python inteiro dentro.

1. Aba **Actions** deste repositório
2. **Build Windows executable** → botão **Run workflow**
3. Quando terminar, baixe o artefato **SocialWars-windows**
4. Descompacte e ponha o `SocialWars.exe` na pasta do jogo
5. Clique duas vezes

São ~13 MB e **não pede administrador**.

<details>
<summary>Por que não tem um .exe pronto aqui?</summary>

O PyInstaller não faz compilação cruzada: um `.exe` de Windows só pode ser
gerado no Windows. O workflow usa uma máquina Windows do GitHub para isso —
de graça, e sem precisar de permissão na sua.

Se você tem Python e quer gerar por conta própria:

```bash
pip install pyinstaller
python build_exe/construir.py
```
</details>

### "Não tenho navegador com Flash"

O jogo é Flash, então precisa de *alguma* coisa que rode Flash. Em ordem do
mais fácil para o mais trabalhoso:

**1. Veja se o Flash já está na sua máquina.** Quem já teve Flash instalado
normalmente tem este arquivo, que é um Flash Player completo e não precisa
instalar nada:

```
C:\Windows\SysWOW64\Macromed\Flash\FlashPlayerApp.exe
```

O lançador procura por ele sozinho:

```bash
python play.py --list-browsers
```

Se aparecer na lista, é só rodar normalmente — ele abre o jogo **sem
navegador nenhum**.

**2. Use um navegador portátil.** Baixe o
[FlashBrowser](https://github.com/radubirsan/FlashBrowser/releases/latest) (ou
o Flash Player standalone) em qualquer máquina, traga num pendrive e largue
numa pasta chamada `browser/` dentro da pasta do jogo. O lançador encontra.

**3. Instale um navegador com Flash.** As opções estão no `FLASH.md` do
projeto original.

### "Abriu, mas o jogo não carrega"

Abra o endereço manualmente no seu navegador Flash:

```
http://127.0.0.1:5055/jogar
```

Se a porta 5055 estiver ocupada, use outra: `python play.py --port 5056`

---

## Coisas que dá para fazer

### Modo turbo

```bash
python play.py --fps 60
```

Deixa o jogo mais rápido — unidades, combate e animações em velocidade dobrada.

**Não é ganho de qualidade, é velocidade mesmo.** A lógica do Social Wars
conta quadros em vez de tempo, então subir a taxa acelera o jogo inteiro. A
produção de recursos não muda (essa é calculada no servidor). Vem desligado;
a explicação completa, com o código do jogo que comprova, está na
[análise técnica](ANALISE_TECNICA.md#1-a-pergunta-dos-60120-hz--resposta-honesta).

### Traduzir para português

```bash
python ferramentas/gerar_mod_traducao.py --ativar
```

Traduz os nomes de construções, unidades e objetivos ("Wood Factory I" →
"Fábrica de Madeira I"). O que o dicionário não cobre continua em inglês — é
só editar o `mods/ptbr.json` aos poucos.

### Recuperar um save

O SW Boost guarda cópias automáticas em `save_backups/`. Veja
[como restaurar](MANUAL.md#recuperar-um-save-corrompido).

---

## O que melhorou

- **Abrir o jogo**: um clique, em vez de servidor + navegador + login
- **Carregamento**: a configuração do jogo caiu de 1,0 MB para 60 KB, e os
  assets deixam de ser pedidos de novo a cada partida
- **Saves**: gravação segura contra corrupção, com backups automáticos

Os números medidos estão no [manual](MANUAL.md#desempenho-medido).

---

## Mais informações

| Documento | Para quê |
| --- | --- |
| [MANUAL.md](MANUAL.md) | Todas as opções, ferramentas e configuração |
| [ANALISE_TECNICA.md](ANALISE_TECNICA.md) | Como o jogo funciona por dentro e o que foi descoberto |
| [IDEIAS.md](IDEIAS.md) | O que ainda dá para melhorar no jogo |

---

## Licença e créditos

O jogo e o servidor de preservação são do
[projeto Social Warriors](https://github.com/AcidCaos/socialwarriors), sob
**GPL v3**. Este material é uma camada de melhorias construída em cima dele e
segue a mesma licença.

*Social Wars* é uma obra da Social Point. Este é um projeto de preservação
sem fins lucrativos.

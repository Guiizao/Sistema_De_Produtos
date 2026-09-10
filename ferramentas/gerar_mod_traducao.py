#!/usr/bin/env python3
"""Gera o esqueleto de um mod de traducao para o Social Wars.

Boa parte do texto que aparece no jogo nao esta dentro do SWF: nomes de
construcoes e unidades (`items[].name`) e os objetivos (`goals[].title`,
`.hint`, `.description`) vem do `config/main.json`, servido pelo servidor.
Isso pode ser traduzido pelo sistema de mods que o projeto ja tem, sem tocar
em nenhum arquivo Flash.

    python ferramentas/gerar_mod_traducao.py --saida mods/ptbr.json

Depois, acrescente a linha `ptbr` no arquivo `mods/mods.txt`.

O arquivo gerado ja vem com os termos mais comuns traduzidos (ver
DICIONARIO). O resto sai em ingles, para ser traduzido aos poucos: o jogo
continua funcionando normalmente enquanto isso, so com parte dos nomes ainda
em ingles. Rodar de novo preserva o que voce ja traduziu.

IMPORTANTE - os caminhos do jsonpatch sao por indice de array, e o servidor
aplica os patches de `config/patch/` ANTES dos mods (o que leva o catalogo de
778 para 900 itens). Por isso esta ferramenta repete o mesmo pipeline antes
de calcular os indices. Consequencia pratica: se voce mudar os patches ou
acrescentar um mod que insere/remove itens, gere o arquivo de novo, e deixe
a linha do mod de traducao ANTES desses outros mods no `mods.txt`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# Termos que se repetem em dezenas de nomes. A substituicao respeita limites
# de palavra, e as expressoes mais longas sao aplicadas primeiro - por isso
# "Wood Factory" vira "Fabrica de Madeira" e nao "Madeira Fabrica".
DICIONARIO = {
    # expressoes compostas (aplicadas antes das palavras soltas)
    "Wood Factory": "Fábrica de Madeira",
    "Steel Factory": "Fábrica de Aço",
    "Oil Factory": "Fábrica de Petróleo",
    "Gold Factory": "Fábrica de Ouro",
    "Gold Mine": "Mina de Ouro",
    "Stone Mine": "Mina de Pedra",
    "Wood Depot": "Depósito de Madeira",
    "Steel Depot": "Depósito de Aço",
    "Oil Depot": "Depósito de Petróleo",
    "Gold Depot": "Depósito de Ouro",
    "Town Hall": "Prefeitura",
    "Tank Academy": "Academia de Tanques",
    "Small Harbour": "Porto Pequeno",
    "Research Center": "Centro de Pesquisa",
    "Soul Mixer": "Misturador de Almas",
    "Watch Tower": "Torre de Vigia",

    # palavras soltas
    "House": "Casa",
    "Barracks": "Quartel",
    "Barrack": "Quartel",
    "Tower": "Torre",
    "Wall": "Muro",
    "Gate": "Portão",
    "Bridge": "Ponte",
    "Market": "Mercado",
    "Hospital": "Hospital",
    "Depot": "Depósito",
    "Silo": "Silo",
    "Mine": "Mina",
    "Factory": "Fábrica",
    "Farm": "Fazenda",
    "Garage": "Garagem",
    "Academy": "Academia",
    "Warehouse": "Armazém",
    "Townhall": "Prefeitura",
    "Harbour": "Porto",
    "Wood": "Madeira",
    "Steel": "Aço",
    "Gold": "Ouro",
    "Oil": "Petróleo",
    "Stone": "Pedra",
    "Soldier": "Soldado",
    "Sniper": "Franco-atirador",
    "Tank": "Tanque",
    "Medic": "Médico",
    "Mechanic": "Mecânico",
    "Engineer": "Engenheiro",
    "Fireman": "Bombeiro",
    "Spy": "Espião",
    "Peasant": "Camponês",
    "Worker": "Trabalhador",
    "Hero": "Herói",
    "Boss": "Chefe",
    "Small": "Pequeno",
    "Large": "Grande",
    "Big": "Grande",
}

# Campos de texto que valem a pena traduzir, por secao do config.
CAMPOS = {
    "items": ("name",),
    "goals": ("title", "hint", "description"),
    "inventory_items": ("name",),
    "collections": ("name",),
}


def carregar_config_efetiva(caminho_config: str) -> tuple[dict, list]:
    """Le o config como o servidor o vera no momento em que os mods rodam.

    O `get_game_config.py` carrega o `main.json`, aplica os patches listados
    em `config/patch/patches.txt` e so entao aplica os mods. Calcular indices
    a partir do `main.json` cru apontaria para os itens errados.
    """
    with open(caminho_config, encoding="utf-8") as handle:
        config = json.load(handle)

    pasta = os.path.join(os.path.dirname(caminho_config), "patch")
    lista = os.path.join(pasta, "patches.txt")
    aplicados = []
    if not os.path.isfile(lista):
        return config, aplicados

    try:
        import jsonpatch
    except ImportError:
        print("[!] jsonpatch nao esta instalado: os patches de config nao foram")
        print("    aplicados e os indices podem apontar para os itens errados.")
        print("    Rode: pip install jsonpatch")
        return config, aplicados

    with open(lista, encoding="utf-8") as handle:
        for linha in handle:
            nome = linha.strip()
            if not nome or nome.startswith("#"):
                continue
            arquivo = os.path.join(pasta, nome.replace(".json", "") + ".json")
            if not os.path.isfile(arquivo):
                continue
            with open(arquivo, encoding="utf-8") as origem:
                jsonpatch.apply_patch(config, json.load(origem), in_place=True)
            aplicados.append(nome)

    return config, aplicados


def verificar(config: dict, operacoes: list) -> list:
    """Confere que todo caminho gerado existe e aponta para um texto."""
    problemas = []
    for operacao in operacoes:
        secao, indice, campo = operacao["path"].lstrip("/").split("/")
        try:
            alvo = config[secao][int(indice)][campo]
        except (KeyError, IndexError, ValueError):
            problemas.append(operacao["path"])
            continue
        if not isinstance(alvo, str):
            problemas.append(operacao["path"])
    return problemas


def traduzir(texto: str) -> str:
    """Aplica o dicionario de termos comuns, preservando o resto do nome."""
    resultado = texto
    # Termos mais longos primeiro, para "Town Hall" ganhar de "Hall".
    for ingles, portugues in sorted(DICIONARIO.items(), key=lambda p: -len(p[0])):
        resultado = re.sub(rf"\b{re.escape(ingles)}\b", portugues, resultado)
    return resultado


def carregar_existente(caminho: str) -> dict:
    """Le um mod ja gerado e devolve {caminho_json: valor} do que foi traduzido."""
    if not os.path.isfile(caminho):
        return {}
    try:
        with open(caminho, encoding="utf-8") as handle:
            patch = json.load(handle)
    except (OSError, ValueError):
        return {}
    return {
        entrada["path"]: entrada["value"]
        for entrada in patch
        if isinstance(entrada, dict) and "path" in entrada and "value" in entrada
    }


def gerar(config: dict, ja_traduzido: dict) -> tuple[list, int, int]:
    operacoes = []
    mantidos = novos = 0

    for secao, campos in CAMPOS.items():
        entradas = config.get(secao)
        if not isinstance(entradas, list):
            continue

        for indice, entrada in enumerate(entradas):
            if not isinstance(entrada, dict):
                continue
            for campo in campos:
                original = entrada.get(campo)
                if not isinstance(original, str) or not original.strip():
                    continue

                caminho = f"/{secao}/{indice}/{campo}"
                if caminho in ja_traduzido:
                    valor = ja_traduzido[caminho]  # respeita o trabalho manual
                    mantidos += 1
                else:
                    valor = traduzir(original)
                    novos += 1

                operacoes.append({"op": "replace", "path": caminho, "value": valor})

    return operacoes, mantidos, novos


def ativar_no_mods_txt(caminho_mods_txt: str, nome: str) -> str:
    """Acrescenta o mod ao mods.txt. Devolve uma mensagem do que aconteceu.

    Cuidado com o arquivo do projeto original: ele nao termina em quebra de
    linha, entao um append ingenuo cola o nome no fim do ultimo comentario e
    o mod nunca e carregado.
    """
    if not os.path.isfile(caminho_mods_txt):
        return f"nao encontrei {caminho_mods_txt}; acrescente '{nome}' a mao"

    with open(caminho_mods_txt, encoding="utf-8") as handle:
        conteudo = handle.read()

    for linha in conteudo.splitlines():
        if linha.strip() == nome:
            return f"'{nome}' ja estava ativo em {caminho_mods_txt}"

    prefixo = "" if conteudo.endswith("\n") or not conteudo else "\n"
    with open(caminho_mods_txt, "a", encoding="utf-8") as handle:
        handle.write(f"{prefixo}{nome}\n")
    return f"'{nome}' ativado em {caminho_mods_txt}"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="config/main.json",
                        help="caminho do config do jogo (padrao: config/main.json)")
    parser.add_argument("--saida", default="mods/ptbr.json",
                        help="arquivo do mod a gerar (padrao: mods/ptbr.json)")
    parser.add_argument("--ativar", action="store_true",
                        help="ja acrescentar o mod ao mods.txt")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.config):
        print(f"[!] Nao encontrei {args.config}.")
        print("    Rode este comando de dentro da pasta do jogo, ou use --config.")
        return 1

    config, patches = carregar_config_efetiva(args.config)
    if patches:
        print(f"[+] Patches de config aplicados antes de indexar: {', '.join(patches)}")

    ja_traduzido = carregar_existente(args.saida)
    operacoes, mantidos, novos = gerar(config, ja_traduzido)

    if not operacoes:
        print("[!] Nenhum texto encontrado no config. O arquivo esta correto?")
        return 1

    problemas = verificar(config, operacoes)
    if problemas:
        print(f"[!] {len(problemas)} caminhos nao batem com o config. Nada foi gravado.")
        for caminho in problemas[:5]:
            print(f"      {caminho}")
        return 1

    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    with open(args.saida, "w", encoding="utf-8") as handle:
        json.dump(operacoes, handle, indent="\t", ensure_ascii=False)
        handle.write("\n")

    nome = os.path.splitext(os.path.basename(args.saida))[0]
    print(f"[+] {args.saida}: {len(operacoes)} textos")
    print(f"      {mantidos} preservados da versao anterior")
    print(f"      {novos} gerados pelo dicionario (revise e ajuste a mao)")
    if args.ativar:
        mods_txt = os.path.join(os.path.dirname(args.saida) or ".", "mods.txt")
        print(f"\n[+] {ativar_no_mods_txt(mods_txt, nome)}")
    else:
        print(f"\n[+] Para ativar, acrescente esta linha em mods/mods.txt:\n      {nome}")
        print("    (ou rode de novo com --ativar)")
    print("    Deixe-a ANTES de mods que acrescentem ou removam itens.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

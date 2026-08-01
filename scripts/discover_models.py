#!/usr/bin/env python3
"""Comparar as fontes de descoberta com o catálogo e listar candidatos por decidir.

A secção 5B do AGENTS.md exige redescobrir o mercado, não só monitorizar o que já
está registado. A parte mecânica dessa redescoberta é sempre a mesma: ler o radar
secundário, extrair pares (marca, modelo) e ver quais é que o catálogo ainda não
conhece.

Sobre o guia da EVMag em concreto: a tabela de veículos é preenchida por
JavaScript. Um pedido HTTP simples devolve o cabeçalho da tabela e mais nada, por
isso não existe forma de extrair modelos sem um browser real. Este script deteta
essa situação e di-lo, em vez de devolver lixo. Uma tentativa anterior com
expressões regulares sobre o texto visível produzia candidatos como
"Abarth Aion Alfa Romeo" — que é a lista de marcas do filtro da página, não
automóveis. Um radar que inventa candidatos é pior do que radar nenhum: dá
trabalho a descartar e esconde os verdadeiros.

O que este script nunca faz: adicionar seja o que for ao catálogo. Um candidato
é uma pergunta para o revisor, e cada um tem de ser confirmado em fonte oficial
portuguesa, com fotografia e concessionário, antes de entrar.
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import subprocess
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"


def normalize(value: str) -> str:
    """Comparar sem acentos, maiúsculas nem pontuação: 'Citroën ë-C3' == 'citroen e c3'."""
    stripped = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in stripped if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_only.lower()).split())


BROWSER_TIMEOUT = 120


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CarroLilianaDiscovery/1.0"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", errors="ignore")


def browser_links(url: str) -> list[str] | None:
    """Abrir o radar num browser e devolver os href da página já renderizada.

    Os dois radares são inúteis sem browser: o guia da EVMag preenche a tabela por
    JavaScript e um pedido HTTP devolve só o cabeçalho; a electrifying.com monta a
    listagem A-Z do mesmo modo. Enquanto isto usava só urllib, a redescoberta de
    mercado — a secção 5B do AGENTS.md — não estava automatizada de todo.
    """
    script = "JSON.stringify([...document.querySelectorAll('a')].map(a => a.getAttribute('href')).filter(Boolean))"
    try:
        opened = subprocess.run(
            ["agent-browser", "open", url], cwd=ROOT, text=True, capture_output=True, timeout=BROWSER_TIMEOUT
        )
        if opened.returncode != 0:
            return None
        result = subprocess.run(
            ["agent-browser", "eval", script], cwd=ROOT, text=True, capture_output=True, timeout=BROWSER_TIMEOUT
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    payload = result.stdout.strip()
    for _ in range(2):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            break
    return payload if isinstance(payload, list) else None


REVIEW_PATH = re.compile(r"/reviews/([^/]+?)(?:-reviews)?/([^/]+)/review")


def models_from_links(links: list[str]) -> list[str]:
    """Pares (marca, modelo) a partir dos URL de review da electrifying.com."""
    found = []
    for href in links:
        match = REVIEW_PATH.search(href or "")
        if match:
            marca, modelo = match.group(1), match.group(2)
            found.append(f"{marca.replace('-', ' ')} {modelo.replace('-', ' ')}")
    return sorted(dict.fromkeys(found))


def table_rows(page: str) -> list[list[str]]:
    """Células de cada linha da primeira tabela da página, sem etiquetas HTML."""
    match = re.search(r"(?is)<table.*?</table>", page)
    if not match:
        return []
    rows = []
    for row in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", match.group(0)):
        cells = [html_module.unescape(re.sub(r"(?s)<[^>]+>", " ", cell)).strip() for cell in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)]
        if cells:
            rows.append(cells)
    return rows


def catalog_keys(catalog: dict) -> set[str]:
    return {normalize(f"{model['brand']} {model['model']}") for model in catalog["models"]}


def unknown_from_names(names: list[str], catalog: dict) -> list[str]:
    known = catalog_keys(catalog)
    unknown = []
    for name in names:
        key = normalize(name)
        if not key or any(key.startswith(existing) or existing.startswith(key) for existing in known):
            continue
        unknown.append(name)
    return sorted(dict.fromkeys(unknown))


def unknown_from_rows(rows: list[list[str]], catalog: dict) -> list[str]:
    """Modelos da tabela do radar que o catálogo ainda não conhece.

    A primeira linha é o cabeçalho e a primeira coluna é o modelo. Um candidato
    conta como conhecido quando partilha o prefixo marca+modelo com uma entrada
    existente: "Kia EV3 GT Line" não é um modelo novo em relação a "Kia EV3".
    """
    known = catalog_keys(catalog)
    unknown = []
    for cells in rows[1:]:
        name = cells[0].strip()
        if not name:
            continue
        key = normalize(name)
        if not key or any(key.startswith(existing) or existing.startswith(key) for existing in known):
            continue
        unknown.append(name)
    return sorted(dict.fromkeys(unknown))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=40, help="quantos candidatos listar")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    manual: list[str] = []
    total = 0

    for source in catalog.get("discovery_sources", []):
        print(f"\nRADAR  {source['name']}\n       {source['url']}")
        try:
            rows = table_rows(fetch(source["url"]))
        except (urllib.error.URLError, TimeoutError, OSError):
            rows = []

        unknown: list[str] = []
        if len(rows) > 1:
            unknown = unknown_from_rows(rows, catalog)
        else:
            # Sem tabela utilizável no HTML: passar ao browser, que renderiza o
            # JavaScript e devolve a listagem completa.
            links = browser_links(source["url"])
            if links is None:
                print("       INACESSÍVEL, mesmo com browser.")
                manual.append(f"{source['name']}: abrir à mão e comparar com o catálogo")
                continue
            nomes = models_from_links(links)
            if not nomes:
                print("       Browser abriu mas não devolveu modelos reconhecíveis.")
                manual.append(f"{source['name']}: abrir à mão e comparar com o catálogo")
                continue
            print(f"       {len(nomes)} modelos lidos no browser.")
            unknown = unknown_from_names(nomes, catalog)
        total += len(unknown)
        if not unknown:
            print("       Nenhum modelo fora do catálogo.")
            continue
        print(f"       {len(unknown)} fora do catálogo:")
        for candidate in unknown[: args.limit]:
            print(f"         - {candidate}")
        if len(unknown) > args.limit:
            print(f"         ... e mais {len(unknown) - args.limit} (usar --limit)")

    print()
    if manual:
        print("POR FAZER À MÃO (a automação não chega aqui):")
        for item in manual:
            print(f"  - {item}")
    print(
        f"{total} candidato(s) extraído(s) automaticamente. Nenhum é prova de nada: "
        "o radar tem lançamentos futuros, comerciais e duplicados. Confirmar cada um "
        "em fonte oficial portuguesa antes de o adicionar (AGENTS.md secções 4 e 7)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

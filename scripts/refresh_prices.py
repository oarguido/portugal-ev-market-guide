#!/usr/bin/env python3
"""Ler as fontes oficiais num browser real e extrair preços, campanhas e validades.

Porque é que isto existe: cerca de um terço das fontes do catálogo — Stellantis,
Tesla, Volvo, Hyundai — devolve HTTP 403 a qualquer cliente que não seja um
browser. Durante muito tempo isso significou que preço e campanha dessas marcas
NÃO eram verificados por nenhuma automação, e o `make links` dizia-se verde na
mesma. Só que a informação sempre lá esteve: um browser a sério entra, e o texto
legal da campanha traz PVPR, PVP de campanha e validade.

Duas ferramentas fazem o trabalho que urllib não faz:

- `agent-browser` abre a página como um browser e devolve o texto renderizado,
  o que resolve as páginas protegidas e as que só existem depois do JavaScript;
- `claude -p` lê esse texto e devolve JSON estruturado, o que resolve o facto de
  cada marca escrever o preço à sua maneira e nenhuma expressão regular aguentar
  quarenta layouts diferentes.

O que este script NUNCA faz: escrever no catálogo sem prova. Cada valor extraído
tem de trazer a citação literal da página de onde saiu, e é verificado — o número
tem de aparecer mesmo no texto, a data tem de ser uma data. Sem citação
verificável a proposta é descartada, porque um modelo a inventar um preço
plausível é exatamente o modo de falha que este projeto não pode ter.

Por omissão só propõe. `--apply` escreve, e apenas as propostas que passaram na
verificação.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
PROPOSALS_PATH = ROOT / "data" / "price_proposals.json"
BROWSER_TIMEOUT = 120
LLM_TIMEOUT = 180
MAX_PAGE_CHARS = 18_000
TODAY = dt.datetime.now(tz=ZoneInfo("Europe/Lisbon")).date().isoformat()

PROMPT = """És um extrator de dados factuais de páginas oficiais de automóveis em Portugal.

Lê o texto abaixo, de {url}, sobre o modelo {model}.

Devolve APENAS um objeto JSON, sem markdown e sem explicações, com estas chaves:

{{
  "campaign_price_vat_incl": número ou null,
  "list_price_vat_incl": número ou null,
  "campaign_valid_until": "AAAA-MM-DD" ou null,
  "campaign_conditions": texto curto ou null,
  "evidence": "a frase literal da página onde os preços aparecem"
}}

Regras absolutas:
- Só extrai valores que estejam LITERALMENTE no texto. Nunca calcules nem estimes.
- "PVPR" e "PVP recomendado" são list_price. "PVP campanha" é campaign_price.
- Preços em euros com IVA, como número (35553.0), sem símbolos nem separadores.
- Se um valor não estiver no texto, mete null. Nunca inventes uma data de validade.
- "evidence" tem de ser copiado à letra do texto, não parafraseado.
- Se a página não falar deste modelo, devolve tudo a null.

TEXTO DA PÁGINA:
{text}
"""


def browser_text(url: str) -> str | None:
    """Abrir num browser real e devolver o texto do body."""
    try:
        opened = subprocess.run(["agent-browser", "open", url], cwd=ROOT, text=True, capture_output=True, timeout=BROWSER_TIMEOUT)
        if opened.returncode != 0:
            return None
        result = subprocess.run(["agent-browser", "get", "text", "body"], cwd=ROOT, text=True, capture_output=True, timeout=BROWSER_TIMEOUT)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    return result.stdout if result.returncode == 0 and result.stdout.strip() else None


def extract(url: str, model: str, text: str) -> dict | None:
    """Pedir ao modelo o JSON estruturado a partir do texto da página."""
    prompt = PROMPT.format(url=url, model=model, text=text[:MAX_PAGE_CHARS])
    try:
        result = subprocess.run(["claude", "-p", prompt], cwd=ROOT, text=True, capture_output=True, timeout=LLM_TIMEOUT)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def digits(value: str) -> str:
    return re.sub(r"\D", "", value)


MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def date_appears(iso: str, page_text: str, haystack: str) -> bool:
    """Uma data ISO raramente aparece assim escrita numa página portuguesa.

    A validade é publicada como "31/08/2026", "31-08-2026" ou "31 de agosto de
    2026". Comparar só a forma ISO rejeitava datas verdadeiras, por isso são
    aceites as representações equivalentes — e nada além delas.
    """
    year, month, day = iso.split("-")
    numeric = {f"{day}{month}{year}", f"{year}{month}{day}", f"{day}{month}{year[2:]}"}
    if any(candidate in haystack for candidate in numeric):
        return True
    extenso = f"{int(day)} de {MESES[int(month) - 1]} de {year}"
    return extenso in " ".join(page_text.split()).lower()


def verify(proposal: dict, page_text: str) -> list[str]:
    """Rejeitar tudo o que não esteja demonstrado no texto da página.

    Esta função é a razão pela qual um modelo de linguagem pode estar neste
    caminho: um preço que o modelo tenha imaginado não aparece no texto, e é aqui
    que morre antes de chegar ao catálogo.
    """
    problems: list[str] = []
    evidence = (proposal.get("evidence") or "").strip()
    if not evidence:
        problems.append("sem citação da página")
    elif evidence not in " ".join(page_text.split()):
        problems.append("a citação não aparece literalmente na página")

    haystack = digits(page_text)
    for field in ("campaign_price_vat_incl", "list_price_vat_incl"):
        price = proposal.get(field)
        if price is None:
            continue
        if not isinstance(price, (int, float)) or price <= 0:
            problems.append(f"{field} não é um preço válido")
            continue
        # O preco tem de aparecer mesmo na pagina, com ou sem separadores.
        if digits(f"{price:.0f}") not in haystack:
            problems.append(f"{field} ({price}) não aparece no texto da página")

    expiry = proposal.get("campaign_valid_until")
    if expiry is not None:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(expiry)):
            problems.append("campaign_valid_until não é uma data ISO")
        elif not date_appears(str(expiry), page_text, haystack):
            problems.append(f"a validade {expiry} não aparece no texto da página")

    if proposal.get("campaign_price_vat_incl") and not proposal.get("campaign_conditions"):
        problems.append("campanha sem condições, e uma campanha sem condições não pode ser publicada")
    return problems


def target_variant(model: dict, proposal: dict) -> dict | None:
    """Qual das variantes é que esta proposta descreve — ou nenhuma.

    Uma página traz um preço; um modelo pode ter várias variantes. Aplicar à
    variante errada é pior do que não aplicar nada, por isso só há duas
    situações seguras: o modelo ter uma única variante, ou o preço extraído já
    coincidir com um preço registado nessa variante (é a mesma oferta, o que
    muda é a validade). Fora disso a proposta fica para uma pessoa decidir.
    """
    variants = model.get("variants", [])
    if len(variants) == 1:
        return variants[0]
    campaign = proposal.get("campaign_price_vat_incl")
    listed = proposal.get("list_price_vat_incl")
    for variant in variants:
        pricing = variant.get("pricing", {})
        known = {pricing.get("particular_campaign_price_vat_incl"), pricing.get("particular_list_price_vat_incl")}
        if (campaign and campaign in known) or (listed and listed in known):
            return variant
    return None


def apply_proposals(catalog: dict, proposals: list[dict]) -> list[str]:
    """Escrever as propostas verificadas, e datar a verificação no que foi tocado."""
    applied: list[str] = []
    for proposal in proposals:
        model = next(
            (m for m in catalog["models"] if m["brand"] == proposal["brand"] and m["model"] == proposal["model"]),
            None,
        )
        if model is None:
            continue
        variant = target_variant(model, proposal)
        label = f"{proposal['brand']} {proposal['model']}"
        if variant is None:
            applied.append(f"AMBÍGUO   {label}: {len(model['variants'])} variantes e o preço não coincide com nenhuma; não aplicado")
            continue
        pricing = variant["pricing"]
        before = (pricing.get("particular_campaign_price_vat_incl"), pricing.get("campaign_valid_until"))
        if proposal.get("campaign_price_vat_incl"):
            pricing["particular_campaign_price_vat_incl"] = proposal["campaign_price_vat_incl"]
            pricing["campaign_valid_until"] = proposal.get("campaign_valid_until")
            if proposal.get("campaign_conditions"):
                pricing["campaign_conditions"] = proposal["campaign_conditions"]
        if proposal.get("list_price_vat_incl"):
            pricing["particular_list_price_vat_incl"] = proposal["list_price_vat_incl"]
        after = (pricing.get("particular_campaign_price_vat_incl"), pricing.get("campaign_valid_until"))
        model["last_verified"] = TODAY
        for source in model.get("data_sources", []):
            source["verified_on"] = TODAY
        verb = "CONFIRMADO" if before == after else "ATUALIZADO"
        applied.append(f"{verb} {label} / {variant['name']}: campanha {after[0]} até {after[1]}")
    return applied


def sources_for(model: dict) -> list[str]:
    return [source["url"] for source in model.get("data_sources", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="limitar a marcas ou modelos que contenham este texto")
    parser.add_argument("--apply", action="store_true", help="escrever as propostas verificadas no catálogo")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    models = catalog["models"]
    if args.only:
        needles = [needle.lower() for needle in args.only]
        models = [m for m in models if any(n in f"{m['brand']} {m['model']}".lower() for n in needles)]

    proposals = []
    for model in models:
        label = f"{model['brand']} {model['model']}"
        for url in sources_for(model):
            print(f"\nLER  {label}\n     {url}")
            text = browser_text(url)
            if not text:
                print("     browser não devolveu texto; fica para revisão humana")
                continue
            proposal = extract(url, label, text)
            if not proposal:
                print("     extração falhou ou não devolveu JSON")
                continue
            problems = verify(proposal, text)
            if problems:
                print("     REJEITADO: " + "; ".join(problems))
                continue
            if not any(proposal.get(field) for field in ("campaign_price_vat_incl", "list_price_vat_incl")):
                print("     sem preços nesta página")
                continue
            proposal.update({"brand": model["brand"], "model": model["model"], "url": url})
            proposals.append(proposal)
            campaign = proposal.get("campaign_price_vat_incl")
            listed = proposal.get("list_price_vat_incl")
            print(f"     VERIFICADO  campanha={campaign} PVP={listed} até {proposal.get('campaign_valid_until')}")

    PROPOSALS_PATH.write_text(json.dumps(proposals, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{len(proposals)} proposta(s) verificada(s) em {PROPOSALS_PATH.relative_to(ROOT)}.")
    if not args.apply:
        print("Nada foi escrito no catálogo. Rever as propostas e repetir com --apply.")
        return 0

    applied = apply_proposals(catalog, proposals)
    print("\n".join(applied) if applied else "Nenhuma proposta pôde ser aplicada sem ambiguidade.")
    if applied:
        CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

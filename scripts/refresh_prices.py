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

O que este script NUNCA faz: promover preços no catálogo. Cada valor extraído
tem de trazer a citação literal da página de onde saiu, e é verificado — o número
tem de aparecer mesmo no texto, a data tem de ser uma data. Sem citação
verificável a proposta é descartada, porque um modelo a inventar um preço
plausível é exatamente o modo de falha que este projeto não pode ter.

Todas as execuções produzem apenas `data/price_proposals.json`. A aceitação numa
fonte v3 exige revisão humana e migração explícita dos dados; `--apply` permanece
aceite por compatibilidade, mas nunca escreve o catálogo.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from browser import page_text as browser_text
from rules import OFFER_CUSTOMERS, OFFER_KINDS, OFFER_VAT_VALUES, evidence_contains_amount, finite_non_negative

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
PROPOSALS_PATH = ROOT / "data" / "price_proposals.json"
LLM_TIMEOUT = 180
MAX_PAGE_CHARS = 18_000
TODAY = dt.datetime.now(tz=ZoneInfo("Europe/Lisbon")).date().isoformat()

PROMPT = """És um extrator de dados factuais de páginas oficiais de automóveis em Portugal.

Lê o texto abaixo, de {url}, sobre o modelo {model}.

Devolve APENAS um objeto JSON, sem markdown e sem explicações, com estas chaves:

{{
  "offers": [
    {{
      "kind": "list_price" ou "campaign_price",
      "amount_eur": número,
      "vat": "included", "excluded" ou "derived",
      "customer": "private", "company" ou "unknown",
      "variant": nome exato da versão ou null,
      "conditions": texto curto ou null,
      "validity": {{"valid_from": "AAAA-MM-DD" ou null, "valid_until": "AAAA-MM-DD" ou null}},
      "evidence": "a frase literal da página onde o montante aparece",
      "derivation": null ou {{"method": "add_vat", "source_amount_eur": número, "vat_rate": número, "result_amount_eur": número}}
    }}
  ]
}}

Regras absolutas:
- Só extrai valores que estejam LITERALMENTE no texto. Nunca calcules nem estimes.
- "PVPR" e "PVP recomendado" são list_price. "PVP campanha" é campaign_price.
- Preços em euros com IVA, como número (35553.0), sem símbolos nem separadores.
- Se um valor não estiver no texto, mete null. Nunca inventes uma data de validade.
- "evidence" tem de ser copiado à letra do texto, não parafraseado.
- Se o IVA estiver excluído ou o cliente não for particular, conserva a oferta como
  proposta de referência; nunca a trates como preço particular elegível.
- Se a página não falar deste modelo, devolve tudo a null.

TEXTO DA PÁGINA:
{text}
"""



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


def _proposal_offers(proposal: dict) -> list[dict]:
    """Ler formato v3 proposto e, temporariamente, o formato plano antigo."""
    offers = proposal.get("offers")
    if isinstance(offers, list):
        return [offer for offer in offers if isinstance(offer, dict)]
    legacy: list[dict] = []
    if proposal.get("list_price_vat_incl") is not None:
        legacy.append(
            {
                "kind": "list_price",
                "amount_eur": proposal.get("list_price_vat_incl"),
                "evidence": proposal.get("evidence"),
                "vat": "included",
                "customer": "private",
            }
        )
    if proposal.get("campaign_price_vat_incl") is not None:
        legacy.append(
            {
                "kind": "campaign_price",
                "amount_eur": proposal.get("campaign_price_vat_incl"),
                "evidence": proposal.get("evidence"),
                "vat": "included",
                "customer": "private",
                "conditions": proposal.get("campaign_conditions"),
                "validity": {"valid_from": None, "valid_until": proposal.get("campaign_valid_until")},
            }
        )
    return legacy


def _verify_offer(offer: dict, page_text: str, index: int) -> list[str]:
    problems: list[str] = []
    label = f"offers[{index}]"
    kind = offer.get("kind")
    if kind not in OFFER_KINDS:
        problems.append(f"{label}.kind inválido")
    amount = offer.get("amount_eur")
    if not finite_non_negative(amount, strictly_positive=True):
        problems.append(f"{label}.amount_eur não é um preço válido")
    raw_evidence = offer.get("evidence")
    evidence = raw_evidence.strip() if isinstance(raw_evidence, str) else ""
    if not evidence:
        problems.append(f"{label} sem citação da página")
    elif evidence not in " ".join(page_text.split()):
        problems.append(f"{label}: a citação não aparece literalmente na página")
    derivation = offer.get("derivation")
    if (
        finite_non_negative(amount, strictly_positive=True)
        and offer.get("vat") != "derived"
        and not evidence_contains_amount(amount, page_text)
    ):
        problems.append(f"{label}.amount_eur ({amount}) não aparece no texto da página")
    vat = offer.get("vat")
    if vat not in OFFER_VAT_VALUES:
        problems.append(f"{label}.vat inválido")
    customer = offer.get("customer")
    if customer not in OFFER_CUSTOMERS:
        problems.append(f"{label}.customer inválido")
    reference_offer = (
        offer.get("classification") == "reference"
        or offer.get("customer") != "private"
        or offer.get("vat") not in {"included", "derived"}
    )
    if kind == "campaign_price" and not reference_offer and not str(offer.get("conditions") or "").strip():
        problems.append(f"{label} campanha sem condições")
    validity = offer.get("validity")
    if validity is not None:
        if not isinstance(validity, dict):
            problems.append(f"{label}.validity inválida")
        else:
            valid_from = validity.get("valid_from")
            if valid_from is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(valid_from)):
                problems.append(f"{label}.validity.valid_from não é uma data ISO")
            expiry = validity.get("valid_until")
            if expiry is not None:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(expiry)):
                    problems.append(f"{label}.validity.valid_until não é uma data ISO")
                elif not date_appears(str(expiry), page_text, digits(page_text)):
                    problems.append(f"a validade {expiry} não aparece no texto da página")
    if vat == "derived":
        if not isinstance(derivation, dict) or derivation.get("method") != "add_vat":
            problems.append(f"{label}: vat=derived exige derivation add_vat")
        elif (
            not finite_non_negative(derivation.get("source_amount_eur"), strictly_positive=True)
            or not finite_non_negative(derivation.get("vat_rate"))
            or not isinstance(derivation.get("vat_rate"), (int, float))
            or derivation["vat_rate"] <= 0
            or derivation["vat_rate"] >= 1
            or not finite_non_negative(derivation.get("result_amount_eur"), strictly_positive=True)
        ):
            problems.append(f"{label}: derivation numérica inválida")
        else:
            from decimal import Decimal

            expected = Decimal(str(derivation["source_amount_eur"])) * (Decimal(1) + Decimal(str(derivation["vat_rate"])))
            if not finite_non_negative(amount, strictly_positive=True):
                problems.append(f"{label}: amount_eur inválido para derivação")
            elif Decimal(str(derivation["result_amount_eur"])) != expected or Decimal(str(amount)) != expected:
                problems.append(f"{label}: derivação não produz amount_eur exatamente")
            elif not evidence_contains_amount(derivation["source_amount_eur"], evidence):
                problems.append(f"{label}: evidence não contém montante sem IVA derivado")
    elif offer.get("derivation") is not None:
        problems.append(f"{label}: derivation só pode existir com vat=derived")
    return problems


def verify(proposal: dict, page_text: str) -> list[str]:
    """Rejeitar tudo o que não esteja demonstrado no texto da página.

    Esta função é a razão pela qual um modelo de linguagem pode estar neste
    caminho: um preço que o modelo tenha imaginado não aparece no texto, e é aqui
    que morre antes de chegar ao catálogo.
    """
    problems = []
    offers = _proposal_offers(proposal)
    for index, offer in enumerate(offers):
        problems.extend(_verify_offer(offer, page_text, index))
    amounts = {
        offer.get("kind"): offer.get("amount_eur")
        for offer in offers
        if finite_non_negative(offer.get("amount_eur"), strictly_positive=True)
    }
    campaign_amount = amounts.get("campaign_price")
    list_amount = amounts.get("list_price")
    if isinstance(campaign_amount, (int, float)) and isinstance(list_amount, (int, float)) and campaign_amount > list_amount:
        problems.append("campanha não pode exceder o PVP")
    return problems


def normalize_proposal(proposal: dict, model: dict, url: str) -> dict:
    """Adicionar proveniência v3 à proposta sem a promover no catálogo."""
    source = next((item for item in model.get("data_sources", []) if item.get("url") == url), {})
    source_type = source.get("type", "official_model")
    source_authority = "authorised_dealer_pt" if "dealer" in source_type else "manufacturer_or_importer_pt"
    normalized: list[dict] = []
    for raw in _proposal_offers(proposal):
        offer = dict(raw)
        customer = offer.get("customer") if offer.get("customer") in OFFER_CUSTOMERS else "unknown"
        audience = "particular" if customer == "private" else "company" if customer == "company" else "unknown"
        vat = offer.get("vat") if offer.get("vat") in {"included", "excluded", "derived"} else None
        private_vat = customer == "private" and vat in {"included", "derived"}
        evidence = offer.get("evidence") if isinstance(offer.get("evidence"), str) else None
        raw_validity = offer.get("validity")
        validity = raw_validity if isinstance(raw_validity, dict) else {"valid_from": None, "valid_until": None}
        valid_until = validity.get("valid_until")
        # Browser extraction is evidence for review, never human confirmation.
        # Keep every normalized proposal in reference cohort until explicit
        # migration into canonical JSON.
        offer["classification"] = "reference"
        offer.update(
            {
                "currency": "EUR",
                "source_url": url,
                "source_authority": source_authority,
                "market": "PT",
                "vat_included": True if private_vat else None,
                "customer": customer,
                "audience": audience,
                "validity": validity,
                "valid_until": valid_until,
                "vat": vat,
                "vat_status": vat or "unknown",
                "evidence": evidence,
                "source_type": source_type,
            }
        )
        offer.setdefault("variant", None)
        offer.setdefault("derivation", None)
        offer["proof"] = {
            "url": url,
            "source_url": url,
            "authority": source_authority,
            "market": "PT",
            "audience": audience,
            "variant": offer.get("variant"),
            "vat_basis": vat or "unknown",
            "literal_excerpt": evidence,
            "status": "verified",
            "source_type": source_type,
            "recorded_on": TODAY,
            "verified_on": TODAY,
            "source_authority": source_authority,
            "customer": customer,
        }
        offer["recorded_on"] = TODAY
        offer["verified_on"] = TODAY
        offer["evidence_record"] = {
            "url": url,
            "source_url": url,
            "market": "PT",
            "recorded_on": TODAY,
            "verified_on": TODAY,
            "literal_excerpt": evidence,
        }
        normalized.append(offer)
    result = {key: value for key, value in proposal.items() if key not in {"offers", "list_price_vat_incl", "campaign_price_vat_incl", "campaign_valid_until", "campaign_conditions"}}
    result["offers"] = normalized
    result.update({"brand": model["brand"], "model": model["model"], "url": url})
    return result


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
    amounts = {offer.get("kind"): offer.get("amount_eur") for offer in _proposal_offers(proposal)}
    campaign = amounts.get("campaign_price")
    listed = amounts.get("list_price")
    for variant in variants:
        pricing = variant.get("pricing", {})
        offers = pricing.get("offers", []) if isinstance(pricing, dict) else []
        known = {offer.get("amount_eur") for offer in offers if isinstance(offer, dict)}
        known.update({pricing.get("particular_campaign_price_vat_incl"), pricing.get("particular_list_price_vat_incl")})
        if (campaign is not None and campaign in known) or (listed is not None and listed in known):
            return variant
    return None


def apply_proposals(catalog: dict, proposals: list[dict]) -> list[str]:
    """Compatibilidade de API: propostas nunca são promovidas por este script."""
    del catalog
    return [
        f"PROPOSTA NÃO APLICADA  {proposal.get('brand', '?')} {proposal.get('model', '?')}: revisão/migração v3 necessária"
        for proposal in proposals
    ]


def sources_for(model: dict) -> list[str]:
    return [source["url"] for source in model.get("data_sources", [])]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", help="limitar a marcas ou modelos que contenham este texto")
    parser.add_argument("--apply", action="store_true", help="compatibilidade antiga; nunca promove propostas")
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
            for offer in _proposal_offers(proposal):
                variant = offer.get("variant")
                if variant is not None and variant not in {item.get("name") for item in model.get("variants", [])}:
                    problems.append(f"variant desconhecida para {label}: {variant}")
            if problems:
                print("     REJEITADO: " + "; ".join(problems))
                continue
            if not _proposal_offers(proposal):
                print("     sem preços nesta página")
                continue
            proposal = normalize_proposal(proposal, model, url)
            proposals.append(proposal)
            print(f"     PROPOSTA  {len(_proposal_offers(proposal))} oferta(s); sem promoção automática")

    PROPOSALS_PATH.write_text(json.dumps(proposals, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        proposal_location = PROPOSALS_PATH.relative_to(ROOT)
    except ValueError:
        proposal_location = PROPOSALS_PATH
    print(f"\n{len(proposals)} proposta(s) verificada(s) em {proposal_location}.")
    print("Nada foi escrito no catálogo. Rever propostas e migrar ofertas v3 explicitamente.")
    if args.apply:
        print("AVISO: --apply foi ignorado; refresh_prices só produz propostas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

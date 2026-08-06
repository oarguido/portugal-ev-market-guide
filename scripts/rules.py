"""Regras partilhadas do contrato de ofertas do catálogo v3.

O catálogo distingue valor confirmado de valor de referência. Só uma oferta
confirmada, para particulares, com IVA incluído (ou derivado exatamente), prova
oficial PT atual e validade em curso pode tornar uma variante elegível.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from decimal import Decimal, InvalidOperation

SCHEMA_VERSION = 3
MAX_PRICE_EUR = 40_000
MAX_AGE_DAYS = 45

OFFER_KINDS = {"list_price", "campaign_price"}
OFFER_CLASSIFICATIONS = {"confirmed", "reference"}
OFFER_PROOF_STATUSES = {"verified", "legacy_unverified"}
OFFER_VAT_VALUES = {"included", "excluded", "derived"}
OFFER_CUSTOMERS = {"private", "company", "unknown"}
SOURCE_AUTHORITIES = {"manufacturer_or_importer_pt", "authorised_dealer_pt"}
ELIGIBILITY_TIERS = {"confirmed_eligible", "potential_reference", "not_demonstrated"}


def finite_non_negative(value: object, *, strictly_positive: bool = False) -> bool:
    """Aceitar números JSON finitos; preços publicados têm de ser positivos."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value) and (value > 0 if strictly_positive else value >= 0)
    except (OverflowError, TypeError):
        return False


def iso_date(value: object) -> dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def decimal(value: object) -> Decimal | None:
    if not finite_non_negative(value):
        return None


def evidence_contains_amount(value: object, evidence: object) -> bool:
    """Confirmar montante literal sem aceitar prefixos numéricos.

    ``30000 in 130000`` era uma falsa prova possível quando se comparavam apenas
    todos os dígitos da frase. Os formatos portugueses mais comuns usam pontos,
    espaços e vírgulas como separadores; converter cada token para Decimal mantém
    a comparação exata sem inventar arredondamentos.
    """
    if not isinstance(evidence, str) or not finite_non_negative(value, strictly_positive=True):
        return False
    target = Decimal(str(value))
    token_pattern = re.compile(r"(?<!\d)(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[,.]\d{1,2})?(?!\d)")
    for match in token_pattern.finditer(evidence):
        token = match.group(0).replace(" ", "")
        if "." in token and "," in token:
            token = token.replace(".", "").replace(",", ".") if token.rfind(",") > token.rfind(".") else token.replace(",", "")
        elif "," in token:
            before, after = token.rsplit(",", 1)
            token = before.replace(",", "") + (f".{after}" if len(after) <= 2 else after)
        elif "." in token:
            parts = token.split(".")
            if len(parts[-1]) == 3 and all(len(part) == 3 for part in parts[1:]):
                token = "".join(parts)
        try:
            if Decimal(token) == target:
                return True
        except InvalidOperation:
            continue
    return False
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def offer_validity(offer: dict) -> tuple[dt.date | None, dt.date | None]:
    validity = offer.get("validity")
    if not isinstance(validity, dict):
        return None, None
    return iso_date(validity.get("valid_from")), iso_date(validity.get("valid_until"))


def offer_is_current(offer: dict, reference: dt.date) -> bool:
    valid_from, valid_until = offer_validity(offer)
    if valid_from is not None and valid_from > reference:
        return False
    return valid_until is None or valid_until >= reference


def offer_is_confirmed_eligible(offer: dict, reference: dt.date) -> bool:
    """Determinar elegibilidade sem confiar num campo editorial pré-calculado."""
    if offer.get("classification") != "confirmed":
        return False
    if offer.get("kind") not in OFFER_KINDS:
        return False
    if offer.get("customer") != "private":
        return False
    if offer.get("vat") not in {"included", "derived"} or offer.get("vat_included") is not True:
        return False
    amount = offer.get("amount_eur")
    if not finite_non_negative(amount, strictly_positive=True):
        return False
    if not isinstance(amount, (int, float)) or amount > MAX_PRICE_EUR:
        return False
    proof = offer.get("proof")
    if not isinstance(proof, dict) or proof.get("status") != "verified":
        return False
    evidence = offer.get("evidence")
    if not isinstance(evidence, str) or not evidence.strip() or proof.get("literal_excerpt") != evidence:
        return False
    if (
        proof.get("url") != offer.get("source_url")
        or proof.get("source_url") != offer.get("source_url")
        or proof.get("authority") != offer.get("source_authority")
        or proof.get("source_authority") != offer.get("source_authority")
        or proof.get("variant") != offer.get("variant")
        or proof.get("customer") != offer.get("customer")
        or proof.get("audience") != offer.get("audience")
    ):
        return False
    if not evidence_contains_amount(amount, evidence):
        return False
    verified = iso_date(proof.get("verified_on"))
    if verified is None or verified > reference or (reference - verified).days > MAX_AGE_DAYS:
        return False
    return offer_is_current(offer, reference)


def offer_is_current_reference(offer: dict, reference: dt.date) -> bool:
    return offer.get("classification") == "reference" and offer_is_current(offer, reference)


def variant_eligibility_tier(variant: dict, reference: dt.date) -> str:
    offers = variant.get("pricing", {}).get("offers", [])
    if not isinstance(offers, list):
        return "not_demonstrated"
    if any(offer_is_confirmed_eligible(offer, reference) for offer in offers if isinstance(offer, dict)):
        return "confirmed_eligible"
    if any(offer_is_current_reference(offer, reference) for offer in offers if isinstance(offer, dict)):
        return "potential_reference"
    return "not_demonstrated"


def effective_confirmed_offer(variant: dict, reference: dt.date) -> dict | None:
    """Escolher campanha atual antes de PVP, apenas dentro da coorte factual."""
    eligible = [
        offer
        for offer in variant.get("pricing", {}).get("offers", [])
        if isinstance(offer, dict) and offer_is_confirmed_eligible(offer, reference)
    ]
    eligible.sort(key=lambda offer: (offer.get("kind") != "campaign_price", offer.get("amount_eur", 0)))
    return eligible[0] if eligible else None

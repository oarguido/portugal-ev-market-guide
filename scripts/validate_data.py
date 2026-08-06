"""Validate the canonical PT BEV catalogue, local images, and source links."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from compile_data import ROOT, load_catalog, load_dealers, vehicle_records
from rules import (
    ELIGIBILITY_TIERS,
    MAX_AGE_DAYS,
    MAX_PRICE_EUR,
    OFFER_CLASSIFICATIONS,
    OFFER_CUSTOMERS,
    OFFER_KINDS,
    OFFER_PROOF_STATUSES,
    OFFER_VAT_VALUES,
    SOURCE_AUTHORITIES,
    effective_confirmed_offer,
    evidence_contains_amount,
    finite_non_negative,
    iso_date,
    variant_eligibility_tier,
)

# Data local portuguesa: campanhas e verificacoes sao datadas no fuso do mercado.
TODAY = dt.datetime.now(tz=ZoneInfo("Europe/Lisbon")).date()
# 200/301/302 provam que a ligacao esta viva E que o conteudo foi lido.
VERIFIED_LINK_CODES = {200, 301, 302}
# 403/429 = anti-bot; 408 = sem resposta a urllib mas acessivel no browser (ver
# check_link). A ligacao nao esta quebrada, mas tambem NAO prova que a pagina
# continua igual: exige revisao no browser (AGENTS.md secao 4).
BLOCKED_LINK_CODES = {403, 408, 429}
# 100 fontes em serie com timeout de 30 s levam minutos; mini.pt sozinho custa 4
# timeouts completos. Verificar em paralelo mantem o resultado igual e ordenado.
LINK_WORKERS = 8
# 13 das 54 fotografias pesam 71 % dos 23 MB da pasta. O orcamento e um aviso,
# nao um erro: uma fotografia oficial correta e mais importante que o peso.
MIN_IMAGE_WIDTH = 600
MAX_IMAGE_BYTES = 500_000
MAX_IMAGE_TOTAL_BYTES = 12_000_000
MODEL_REQUIRED = {
    "brand",
    "model",
    "release_year",
    "powertrain",
    "segment",
    "availability_status",
    "eligibility_status",
    "eligibility_tier",
    "eligibility_reason",
    "official_link",
    "image_path",
    "last_verified",
    "data_sources",
    "variants",
    "dimensions",
    "luggage_capacity",
    "pros",
    "cons",
}
VARIANT_REQUIRED = {"name", "battery_capacity_kwh", "wltp_range_combined_km", "power_kw", "power_hp", "pricing", "eligibility_status", "eligibility_tier", "battery_technology"}
DEALER_REQUIRED = {"brand", "name", "address", "postal_code", "locality", "phone", "email", "official_url", "maps_url", "services", "verified_on"}
DISCOVERY_REQUIRED = {"name", "url", "type", "verified_on", "usage_policy", "known_limitations"}
BATTERY_TECH_STRING_FIELDS = ("chemistry", "generation", "architecture")
BATTERY_TECH_BOOLEAN_FIELDS = ("heat_pump_included", "battery_preheating")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
EMPTY_CONDITION_MARKERS = {"", "n/a", "n/d", "na", "null", "por confirmar", "a confirmar", "sem condições"}
OFFER_REQUIRED = {
    "kind",
    "classification",
    "amount_eur",
    "currency",
    "source_url",
    "source_authority",
    "market",
    "variant",
    "conditions",
    "vat_included",
    "proof",
    "derivation",
    "recorded_on",
    "verified_on",
    "customer",
    "audience",
    "validity",
    "valid_until",
    "vat",
    "vat_status",
    "evidence",
    "evidence_record",
    "source_type",
}
OFFER_AUDIENCES = {"particular", "company", "unknown"}
EXPECTED_ELIGIBILITY_STATUSES = ["confirmed_eligible", "potential_reference", "not_demonstrated"]
PROOF_REQUIRED = {
    "url",
    "source_url",
    "authority",
    "market",
    "audience",
    "variant",
    "vat_basis",
    "literal_excerpt",
    "status",
    "source_type",
    "recorded_on",
    "verified_on",
    "source_authority",
    "customer",
}
VALIDITY_REQUIRED = {"valid_from", "valid_until"}


def image_dimensions(path) -> tuple[str, int, int] | None:
    """(formato, largura, altura) lendo só o cabeçalho, ou None se ilegível.

    O tamanho em bytes não chega para saber se uma fotografia presta. Uma captura
    falhada da Stellantis trazia 4,4 KB de placeholder e passava no limite de
    5 KB por pouco; um ficheiro truncado a meio do download passa à mesma. Ler o
    cabeçalho responde à pergunta certa: isto é mesmo uma imagem, e do formato
    que a extensão promete?

    Feito à mão porque o projeto não tem dependências e não vale a pena ganhar
    uma só para ler três cabeçalhos.
    """
    try:
        header = path.read_bytes()[:32]
    except OSError:
        return None
    if header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR":
        return "png", int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    if header[:2] == b"\xff\xd8":
        return _jpeg_dimensions(path)
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return _webp_dimensions(path)
    return None


def _jpeg_dimensions(path) -> tuple[str, int, int] | None:
    data = path.read_bytes()
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        # SOF0..SOF15, excluindo DHT (C4), JPG (C8) e DAC (CC).
        if 0xC0 <= marker <= 0xCF and marker not in {0xC4, 0xC8, 0xCC}:
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            return "jpeg", width, height
        index += 2 + int.from_bytes(data[index + 2 : index + 4], "big")
    return None


def _webp_dimensions(path) -> tuple[str, int, int] | None:
    data = path.read_bytes()[:40]
    chunk = data[12:16]
    if chunk == b"VP8 ":
        return "webp", int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return "webp", (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":
        return "webp", int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    return None


EXTENSION_FORMAT = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}


def effective_price(pricing: dict, reference: dt.date | None = None) -> float | None:
    """Devolver apenas preço confirmado atual; referências nunca são elegíveis."""
    offer = effective_confirmed_offer({"pricing": pricing}, reference or TODAY)
    return offer.get("amount_eur") if offer else None


def _amount_tokens(value: object) -> set[str]:
    if not finite_non_negative(value, strictly_positive=True):
        return set()
    if not isinstance(value, (int, float)):
        return set()
    raw = str(value)
    tokens = {re.sub(r"\D", "", raw)}
    if isinstance(value, (int, float)) and float(value).is_integer():
        tokens.add(str(int(value)))
    else:
        tokens.add(re.sub(r"\D", "", f"{float(value):.2f}"))
    return {token for token in tokens if token}


def _literal_amount_in_evidence(value: object, evidence: str) -> bool:
    return evidence_contains_amount(value, evidence)


def _validate_derivation(offer: dict, label: str, evidence: str) -> list[str]:
    errors: list[str] = []
    derivation = offer.get("derivation")
    if offer.get("vat") != "derived":
        if derivation is not None:
            errors.append(f"{label}: derivation só pode existir com vat=derived")
        return errors
    if not isinstance(derivation, dict):
        return [f"{label}: vat=derived exige derivation"]
    required = {"method", "source_amount_eur", "vat_rate", "result_amount_eur"}
    missing = required - derivation.keys()
    if missing:
        return [f"{label}: derivation com campos em falta: {sorted(missing)}"]
    if derivation.get("method") != "add_vat":
        errors.append(f"{label}: derivation.method tem de ser add_vat")
    source_raw = derivation.get("source_amount_eur")
    rate_raw = derivation.get("vat_rate")
    result_raw = derivation.get("result_amount_eur")
    source = source_raw if isinstance(source_raw, (int, float)) else 0
    rate = rate_raw if isinstance(rate_raw, (int, float)) else 0
    result = result_raw if isinstance(result_raw, (int, float)) else 0
    if not finite_non_negative(source_raw, strictly_positive=True):
        errors.append(f"{label}: derivation.source_amount_eur inválido")
    if not finite_non_negative(rate_raw) or not isinstance(rate_raw, (int, float)) or rate <= 0 or rate >= 1:
        errors.append(f"{label}: derivation.vat_rate inválido")
    if not finite_non_negative(result_raw, strictly_positive=True):
        errors.append(f"{label}: derivation.result_amount_eur inválido")
    if not finite_non_negative(offer.get("amount_eur"), strictly_positive=True):
        errors.append(f"{label}: amount_eur inválido para derivação")
    if not errors:
        from decimal import Decimal

        expected = Decimal(str(source)) * (Decimal(1) + Decimal(str(rate)))
        if Decimal(str(result)) != expected or Decimal(str(offer.get("amount_eur"))) != expected:
            errors.append(f"{label}: derivação de IVA não produz amount_eur exatamente")
        if not _literal_amount_in_evidence(source, evidence):
            errors.append(f"{label}: evidence não contém literalmente o montante sem IVA derivado")
    return errors


def validate_offer(
    offer: object,
    label: str,
    model: dict,
    variant_name: str,
    reference: dt.date | None = None,
) -> list[str]:
    """Validar oferta v3 canónica e matriz confirmed/reference."""
    reference = reference or TODAY
    if not isinstance(offer, dict):
        return [f"{label}: oferta tem de ser um objeto"]
    errors: list[str] = []
    missing = OFFER_REQUIRED - offer.keys()
    if missing:
        errors.append(f"{label}: campos em falta: {sorted(missing)}")

    kind = offer.get("kind")
    classification = offer.get("classification")
    amount = offer.get("amount_eur")
    if kind not in OFFER_KINDS:
        errors.append(f"{label}: kind inválido")
    if classification not in OFFER_CLASSIFICATIONS:
        errors.append(f"{label}: classification inválida")
    if not finite_non_negative(amount, strictly_positive=True):
        errors.append(f"{label}: amount_eur tem de ser finito e positivo")
    if offer.get("currency") != "EUR":
        errors.append(f"{label}: currency tem de ser EUR")
    if offer.get("source_authority") not in SOURCE_AUTHORITIES:
        errors.append(f"{label}: source_authority inválido")
    if offer.get("market") != "PT":
        errors.append(f"{label}: market tem de ser PT")
    if offer.get("vat") not in OFFER_VAT_VALUES | {None}:
        errors.append(f"{label}: vat inválido")
    vat_included = offer.get("vat_included")
    if vat_included is not None and not isinstance(vat_included, bool):
        errors.append(f"{label}: vat_included tem de ser booleano ou null")
    if offer.get("vat_status") not in {"included", "excluded", "derived", "unknown"}:
        errors.append(f"{label}: vat_status inválido")
    if offer.get("vat") in {"included", "derived"} and vat_included is not True:
        errors.append(f"{label}: vat={offer.get('vat')} exige vat_included=true")
    if offer.get("vat") == "included" and offer.get("vat_status") != "included":
        errors.append(f"{label}: vat_status não coincide com vat")
    if offer.get("vat") == "derived" and offer.get("vat_status") != "derived":
        errors.append(f"{label}: vat_status não coincide com vat")
    if offer.get("vat") == "excluded" and offer.get("vat_status") != "excluded":
        errors.append(f"{label}: vat_status não coincide com vat")
    if offer.get("vat") is None and offer.get("vat_status") != "unknown":
        errors.append(f"{label}: vat=null exige vat_status=unknown")
    if offer.get("customer") not in OFFER_CUSTOMERS:
        errors.append(f"{label}: customer inválido")
    if offer.get("audience") not in OFFER_AUDIENCES:
        errors.append(f"{label}: audience inválido")
    if offer.get("variant") != variant_name:
        errors.append(f"{label}: variant tem de coincidir exatamente com {variant_name!r}")

    conditions = offer.get("conditions")
    if kind == "campaign_price" and classification == "confirmed":
        normalized = " ".join(conditions.split()).casefold() if isinstance(conditions, str) else ""
        if normalized in EMPTY_CONDITION_MARKERS:
            errors.append(f"{label}: campanha sem condições materiais")
    elif conditions is not None and (not isinstance(conditions, str) or not conditions.strip()):
        errors.append(f"{label}: conditions tem de ser texto não vazio ou null")

    validity = offer.get("validity")
    parsed_from = parsed_until = None
    if not isinstance(validity, dict):
        errors.append(f"{label}: validity tem de ser um objeto")
    else:
        missing_validity = VALIDITY_REQUIRED - validity.keys()
        if missing_validity:
            errors.append(f"{label}: validity com campos em falta: {sorted(missing_validity)}")
        valid_from = validity.get("valid_from")
        valid_until = validity.get("valid_until")
        parsed_from = None if valid_from is None else iso_date(valid_from)
        parsed_until = None if valid_until is None else iso_date(valid_until)
        if valid_from is not None and parsed_from is None:
            errors.append(f"{label}: validity.valid_from inválido")
        if valid_until is not None and parsed_until is None:
            errors.append(f"{label}: validity.valid_until inválido")
        if parsed_from and parsed_until and parsed_until < parsed_from:
            errors.append(f"{label}: validity termina antes de começar")
    if offer.get("valid_until") != (validity.get("valid_until") if isinstance(validity, dict) else None):
        errors.append(f"{label}: valid_until tem de coincidir com validity.valid_until")

    recorded_offer = iso_date(offer.get("recorded_on"))
    verified_offer = iso_date(offer.get("verified_on")) if offer.get("verified_on") is not None else None
    if recorded_offer is None or recorded_offer > reference:
        errors.append(f"{label}: recorded_on inválido ou futuro")
    if offer.get("verified_on") is not None and verified_offer is None:
        errors.append(f"{label}: verified_on inválido")

    source_url = offer.get("source_url")
    source_types = {source.get("url"): source.get("type") for source in model.get("data_sources", []) if isinstance(source, dict)}
    parsed_source = urlparse(source_url or "")
    if parsed_source.scheme != "https" or not parsed_source.netloc:
        errors.append(f"{label}: source_url não é HTTPS")
    if source_url not in source_types:
        errors.append(f"{label}: source_url não está em data_sources do modelo")
    elif offer.get("source_type") != source_types[source_url]:
        errors.append(f"{label}: source_type não coincide com data_sources")

    proof = offer.get("proof")
    if not isinstance(proof, dict):
        errors.append(f"{label}: proof tem de ser um objeto")
        proof = {}
    missing_proof = PROOF_REQUIRED - proof.keys()
    if missing_proof:
        errors.append(f"{label}: proof com campos em falta: {sorted(missing_proof)}")
    if proof.get("status") not in OFFER_PROOF_STATUSES:
        errors.append(f"{label}: proof.status inválido")
    if proof.get("url") != source_url or proof.get("source_url") != source_url:
        errors.append(f"{label}: proof URL não coincide com source_url")
    if proof.get("authority") != offer.get("source_authority") or proof.get("source_authority") != offer.get("source_authority"):
        errors.append(f"{label}: proof authority não coincide com source_authority")
    if proof.get("source_type") != offer.get("source_type"):
        errors.append(f"{label}: proof.source_type não coincide com oferta")
    if proof.get("market") != "PT" or proof.get("market") != offer.get("market"):
        errors.append(f"{label}: proof.market tem de ser PT e coincidir com oferta")
    if proof.get("audience") != offer.get("audience") or proof.get("customer") != offer.get("customer"):
        errors.append(f"{label}: proof público não coincide com oferta")
    if proof.get("variant") != offer.get("variant"):
        errors.append(f"{label}: proof.variant não coincide com oferta")
    expected_vat_basis = offer.get("vat") if offer.get("vat") in OFFER_VAT_VALUES else "unknown"
    if proof.get("vat_basis") != expected_vat_basis:
        errors.append(f"{label}: proof.vat_basis não coincide com vat")
    if proof.get("literal_excerpt") != offer.get("evidence"):
        errors.append(f"{label}: proof.literal_excerpt não coincide com evidence")
    recorded_proof = iso_date(proof.get("recorded_on"))
    verified_proof = iso_date(proof.get("verified_on")) if proof.get("verified_on") is not None else None
    if recorded_proof != recorded_offer:
        errors.append(f"{label}: proof.recorded_on tem de coincidir com oferta")
    if verified_proof != verified_offer:
        errors.append(f"{label}: proof.verified_on tem de coincidir com oferta")

    evidence = offer.get("evidence")
    evidence_record = offer.get("evidence_record")
    if not isinstance(evidence_record, dict):
        errors.append(f"{label}: evidence_record tem de ser um objeto")
    else:
        required_record = {"url", "source_url", "market", "recorded_on", "verified_on", "literal_excerpt"}
        missing_record = required_record - evidence_record.keys()
        if missing_record:
            errors.append(f"{label}: evidence_record com campos em falta: {sorted(missing_record)}")
        if evidence_record.get("url") != source_url or evidence_record.get("source_url") != source_url:
            errors.append(f"{label}: evidence_record URL não coincide com oferta")
        if evidence_record.get("market") != "PT":
            errors.append(f"{label}: evidence_record.market tem de ser PT")
        if evidence_record.get("recorded_on") != offer.get("recorded_on") or evidence_record.get("verified_on") != offer.get("verified_on"):
            errors.append(f"{label}: evidence_record datas não coincidem com oferta")
        if evidence_record.get("literal_excerpt") != evidence:
            errors.append(f"{label}: evidence_record.literal_excerpt não coincide com evidence")

    if classification == "confirmed":
        if proof.get("status") != "verified":
            errors.append(f"{label}: oferta confirmed exige proof.status=verified")
        if offer.get("legacy_unverified") is True:
            errors.append(f"{label}: oferta confirmed não pode ser legacy_unverified")
        if offer.get("customer") != "private" or offer.get("audience") != "particular":
            errors.append(f"{label}: oferta confirmed exige público particular")
        if offer.get("vat") not in {"included", "derived"} or vat_included is not True:
            errors.append(f"{label}: oferta confirmed exige IVA incluído ou derivado")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"{label}: oferta confirmed exige evidence literal")
        elif offer.get("vat") == "included" and not _literal_amount_in_evidence(amount, evidence):
            errors.append(f"{label}: evidence não contém literalmente amount_eur")
        if verified_offer is None or verified_offer > reference:
            errors.append(f"{label}: verified_on inválido ou futuro")
        elif (reference - verified_offer).days > MAX_AGE_DAYS:
            errors.append(f"{label}: prova confirmada com mais de {MAX_AGE_DAYS} dias")
        if verified_offer != iso_date(model.get("last_verified")):
            errors.append(f"{label}: verified_on tem de coincidir com last_verified")
    elif classification == "reference":
        if proof.get("status") not in {"verified", "legacy_unverified"}:
            errors.append(f"{label}: oferta reference exige proof.status=verified ou legacy_unverified")
        if proof.get("status") == "legacy_unverified" and offer.get("verified_on") is not None:
            errors.append(f"{label}: oferta legacy exige verified_on=null")
        if proof.get("status") == "legacy_unverified" and offer.get("legacy_unverified") is not True:
            errors.append(f"{label}: oferta legacy exige legacy_unverified=true")
        if proof.get("status") == "verified" and offer.get("legacy_unverified") is True:
            errors.append(f"{label}: referência atual não pode ser legacy_unverified")
        if proof.get("status") == "verified":
            if verified_offer is None or verified_offer > reference:
                errors.append(f"{label}: referência atual exige verified_on válido")
            elif (reference - verified_offer).days > MAX_AGE_DAYS:
                errors.append(f"{label}: referência atual com mais de {MAX_AGE_DAYS} dias")
        if evidence is not None and (not isinstance(evidence, str) or not evidence.strip()):
            errors.append(f"{label}: evidence de referência tem de ser texto não vazio ou null")
    errors.extend(_validate_derivation(offer, label, evidence if isinstance(evidence, str) else ""))
    return errors


def validate_pricing(
    pricing: object,
    label: str = "preço",
    model: dict | None = None,
    variant_name: str | None = None,
    reference: dt.date | None = None,
    allow_empty: bool = False,
) -> list[str]:
    """Validar pricing.offers[] v3 sem aceitar campos de preço v2."""
    if not isinstance(pricing, dict):
        return [f"{label}: pricing tem de ser um objeto"]
    offers = pricing.get("offers")
    if not isinstance(offers, list):
        return [f"{label}: pricing.offers tem de ser uma lista"]
    if not offers:
        if allow_empty:
            return []
        return [f"{label}: pricing.offers tem de ser uma lista não vazia"]
    model = model or {"data_sources": [], "last_verified": None}
    variant_name = variant_name or label.rsplit(" / ", 1)[-1]
    errors: list[str] = []
    for index, offer in enumerate(offers):
        errors.extend(validate_offer(offer, f"{label} / oferta {index + 1}", model, variant_name, reference))
    amounts = {
        offer.get("kind"): offer.get("amount_eur")
        for offer in offers
        if isinstance(offer, dict) and offer.get("classification") == "confirmed" and finite_non_negative(offer.get("amount_eur"), strictly_positive=True)
    }
    campaign = amounts.get("campaign_price")
    listed = amounts.get("list_price")
    if isinstance(campaign, (int, float)) and isinstance(listed, (int, float)) and campaign > listed:
        errors.append(f"{label}: campanha não pode exceder o PVP")
    return errors


def validate_battery_technology(model: dict, label: str) -> list[str]:
    """Validar campos tecnológicos opcionais sem preencher valores ausentes.

    A UI conhece ``technology_advantages.battery_tech``. Estes campos continuam
    opcionais para que só entre informação documentada; ``null`` é a representação
    de desconhecido e campos novos são preservados sem serem inventados aqui.
    """
    technology = model.get("technology_advantages")
    if technology is None:
        return []
    if not isinstance(technology, dict):
        return [f"{label}: technology_advantages tem de ser um objeto ou null"]
    battery_tech = technology.get("battery_tech")
    if battery_tech is None:
        return []
    if not isinstance(battery_tech, dict):
        return [f"{label}: technology_advantages.battery_tech tem de ser um objeto ou null"]

    errors: list[str] = []
    for field in BATTERY_TECH_STRING_FIELDS:
        value = battery_tech.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"{label}: battery_tech.{field} tem de ser uma string não vazia ou null")
    for field in BATTERY_TECH_BOOLEAN_FIELDS:
        value = battery_tech.get(field)
        if value is not None and not isinstance(value, bool):
            errors.append(f"{label}: battery_tech.{field} tem de ser booleano ou null")
    return errors


def validate_variant_battery_technology(variant: dict, label: str) -> list[str]:
    technology = variant.get("battery_technology")
    if not isinstance(technology, dict):
        return [f"{label}: battery_technology tem de ser um objeto"]
    errors: list[str] = []
    for field in ("chemistry", "generation", "architecture"):
        value = technology.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"{label}: battery_technology.{field} tem de ser string não vazia ou null")
    source_url = technology.get("source_url")
    if source_url is not None:
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{label}: battery_technology.source_url não é HTTPS")
    verified = technology.get("verified_on")
    if verified is not None and iso_date(verified) is None:
        errors.append(f"{label}: battery_technology.verified_on inválido")
    return errors


def validate_catalog_meta(catalog: dict) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != 3:
        errors.append("schema_version tem de ser 3")
    if catalog.get("market") != "PT" or catalog.get("currency") != "EUR":
        errors.append("catálogo tem de usar mercado PT e moeda EUR")
    if iso_date(catalog.get("last_verified")) is None:
        errors.append("last_verified do catálogo inválido")
    scope = catalog.get("scope", {})
    if scope.get("powertrain") != "BEV" or scope.get("vehicle_type") != "M1 passenger car" or scope.get("condition") != "new" or scope.get("maximum_vat_inclusive_price_eur") != MAX_PRICE_EUR:
        errors.append("scope tem de ser M1, novo, exclusivamente BEV e limitado a 40.000 €")
    if scope.get("eligibility_statuses") != EXPECTED_ELIGIBILITY_STATUSES:
        errors.append("scope.eligibility_statuses não declara exatamente os três estados v3")
    for field in ("price_rule", "reference_price_policy", "null_policy"):
        if not isinstance(scope.get(field), str) or not scope[field].strip():
            errors.append(f"scope.{field} obrigatório")
    discovery_sources = catalog.get("discovery_sources", [])
    if not isinstance(discovery_sources, list) or not discovery_sources:
        errors.append("discovery_sources tem de conter pelo menos uma fonte secundária")
    else:
        for source in discovery_sources:
            label = f"Fonte de descoberta {source.get('name', '?')}"
            missing = DISCOVERY_REQUIRED - source.keys()
            if missing:
                errors.append(f"{label}: campos em falta: {sorted(missing)}")
            if source.get("type") != "secondary_market_discovery":
                errors.append(f"{label}: tipo inválido")
            parsed = urlparse(source.get("url", ""))
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{label}: URL não é HTTPS")
            try:
                dt.date.fromisoformat(source.get("verified_on", ""))
            except ValueError:
                errors.append(f"{label}: verified_on inválido")
            if not isinstance(source.get("known_limitations"), list) or not source["known_limitations"]:
                errors.append(f"{label}: limitações não documentadas")
    return errors


def validate_model(model: dict, label: str, seen: set[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    missing = MODEL_REQUIRED - model.keys()
    if missing:
        errors.append(f"{label}: campos em falta: {sorted(missing)}")
    errors.extend(validate_battery_technology(model, label))
    key = (model.get("brand", ""), model.get("model", ""))
    if key in seen:
        errors.append(f"{label}: modelo duplicado")
    seen.add(key)
    if model.get("powertrain") != "BEV":
        errors.append(f"{label}: powertrain não é BEV")
    if model.get("availability_status") != "available":
        errors.append(f"{label}: modelo não está disponível")
    if not isinstance(model.get("release_year"), int) or isinstance(model.get("release_year"), bool) or model.get("release_year", 0) <= 0:
        errors.append(f"{label}: release_year inválido")
    if model.get("eligibility_status") not in ELIGIBILITY_TIERS or model.get("eligibility_tier") not in ELIGIBILITY_TIERS:
        errors.append(f"{label}: eligibility_status/tier inválido")
    if not isinstance(model.get("eligibility_reason"), str) or not model["eligibility_reason"].strip():
        errors.append(f"{label}: eligibility_reason obrigatório")
    try:
        dt.date.fromisoformat(model.get("last_verified", ""))
    except ValueError:
        errors.append(f"{label}: last_verified inválido")
    for field in ("official_link",):
        parsed = urlparse(model.get(field, ""))
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append(f"{label}: {field} não é URL HTTPS")
    image = ROOT / "web" / model.get("image_path", "")
    if not model.get("image_path") or not image.is_file() or image.stat().st_size < 5_000:
        errors.append(f"{label}: imagem local ausente ou inválida ({model.get('image_path')!r})")
    else:
        measured = image_dimensions(image)
        if measured is None:
            errors.append(f"{label}: a fotografia não é uma imagem legível ({model['image_path']})")
        else:
            fmt, width, _ = measured
            expected = EXTENSION_FORMAT.get(image.suffix.lower())
            if expected and fmt != expected:
                errors.append(f"{label}: a fotografia é {fmt} mas a extensão diz {image.suffix}")
            elif width < MIN_IMAGE_WIDTH:
                errors.append(f"{label}: fotografia com apenas {width} px de largura (mínimo {MIN_IMAGE_WIDTH})")
    sources = model.get("data_sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{label}: data_sources vazio")
    else:
        for source in sources:
            if source.get("verified_on") != model.get("last_verified"):
                errors.append(f"{label}: data_sources com data inconsistente")
            if not str(source.get("type", "")).startswith("official_"):
                errors.append(f"{label}: data_source não é oficial ({source.get('type')!r})")
            parsed = urlparse(source.get("url", ""))
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{label}: fonte sem URL HTTPS")
    dims = model.get("dimensions")
    if not isinstance(dims, dict):
        errors.append(f"{label}: 'dimensions' tem de ser um objeto")
    else:
        for dim_key in ("length_mm", "width_mm", "height_mm"):
            val = dims.get(dim_key)
            if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                errors.append(f"{label}: dimensions.{dim_key} tem de ser um inteiro positivo")
    luggage = model.get("luggage_capacity")
    if not isinstance(luggage, dict):
        errors.append(f"{label}: 'luggage_capacity' tem de ser um objeto")
    else:
        boot = luggage.get("boot_capacity_l")
        if not isinstance(boot, int) or isinstance(boot, bool) or boot <= 0:
            errors.append(f"{label}: luggage_capacity.boot_capacity_l tem de ser um inteiro positivo")
        frunk = luggage.get("frunk_capacity_l")
        if frunk is not None and (not isinstance(frunk, int) or isinstance(frunk, bool) or frunk < 0):
            errors.append(f"{label}: luggage_capacity.frunk_capacity_l tem de ser um inteiro não-negativo ou null")
    for list_name in ("pros", "cons"):
        items = model.get(list_name)
        if not isinstance(items, list) or not items:
            errors.append(f"{label}: '{list_name}' tem de ser uma lista não vazia de strings")
        else:
            if not (3 <= len(items) <= 5):
                errors.append(f"{label}: '{list_name}' tem de conter entre 3 e 5 elementos (atual: {len(items)})")
            for item in items:
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"{label}: item em '{list_name}' tem de ser uma string não vazia")
    return errors


def validate_variant(model: dict, variant: dict, vlabel: str, variant_names: set[str]) -> tuple[list[str], str]:
    errors: list[str] = []
    missing = VARIANT_REQUIRED - variant.keys()
    if missing:
        errors.append(f"{vlabel}: campos em falta: {sorted(missing)}")
    errors.extend(validate_variant_battery_technology(variant, vlabel))
    if variant.get("name") in variant_names:
        errors.append(f"{vlabel}: variante duplicada")
    variant_names.add(variant.get("name"))
    for numeric in ("battery_capacity_kwh", "wltp_range_combined_km", "power_kw", "power_hp"):
        if not finite_non_negative(variant.get(numeric), strictly_positive=True):
            errors.append(f"{vlabel}: {numeric} inválido")
    pricing = variant.get("pricing", {})
    allow_empty = isinstance(pricing, dict) and pricing.get("offers") == [] and variant.get("eligibility_status") == "not_demonstrated" and variant.get("eligibility_tier") == "not_demonstrated"
    errors.extend(validate_pricing(pricing, vlabel, model, variant.get("name"), TODAY, allow_empty=allow_empty))
    expected_tier = variant_eligibility_tier(variant, TODAY)
    declared_tier = variant.get("eligibility_tier")
    if declared_tier not in ELIGIBILITY_TIERS:
        errors.append(f"{vlabel}: eligibility_tier inválido")
    elif declared_tier != expected_tier:
        errors.append(f"{vlabel}: eligibility_tier {declared_tier!r} não corresponde a {expected_tier!r}")
    if variant.get("eligibility_status") != expected_tier:
        errors.append(f"{vlabel}: eligibility_status não corresponde a {expected_tier!r}")
    return errors, expected_tier


def validate_catalog(catalog: dict) -> list[str]:
    errors = validate_catalog_meta(catalog)
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        return [*errors, "models tem de ser uma lista não vazia"]

    seen: set[tuple[str, str]] = set()
    for model in models:
        label = f"{model.get('brand', '?')} {model.get('model', '?')}"
        errors.extend(validate_model(model, label, seen))
        variants = model.get("variants")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{label}: variants vazio")
            continue
        variant_names: set[str] = set()
        confirmed_variant = False
        for variant in variants:
            vlabel = f"{label} / {variant.get('name', '?')}"
            variant_errors, expected_tier = validate_variant(model, variant, vlabel, variant_names)
            errors.extend(variant_errors)
            confirmed_variant |= expected_tier == "confirmed_eligible"
        expected_model_tier = (
            "confirmed_eligible" if confirmed_variant else "potential_reference" if any(item.get("eligibility_tier") == "potential_reference" for item in variants) else "not_demonstrated"
        )
        if model.get("eligibility_status") != expected_model_tier or model.get("eligibility_tier") != expected_model_tier:
            errors.append(f"{label}: eligibility_status/tier não corresponde a {expected_model_tier!r}")
    return errors


def duplicate_image_errors(catalog: dict) -> list[str]:
    """Dois modelos com a mesma fotografia byte a byte: um deles está errado.

    Aconteceu duas vezes. Três Opel diferentes ficaram com o mesmo placeholder de
    4 KB, e o MINI Aceman ficou com a fotografia de um Fiat 500e cor-de-rosa
    porque a captura reutilizou a página anterior. Nenhuma verificação de
    cabeçalho ou de tamanho apanha isto — os ficheiros são imagens válidas de
    carros a sério, só que do carro errado.

    Comparar os digests é barato e apanha a família toda de enganos.
    """
    from collections import defaultdict

    digests: dict[str, list[str]] = defaultdict(list)
    for model in catalog.get("models", []):
        image = ROOT / "web" / model.get("image_path", "")
        if not image.is_file():
            continue
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        digests[digest].append(f"{model.get('brand', '?')} {model.get('model', '?')}")
    return [f"fotografia repetida em modelos diferentes: {', '.join(sorted(nomes))}" for nomes in digests.values() if len(nomes) > 1]


def validate_dealers(catalog: dict, dealer_catalog: dict) -> list[str]:
    errors: list[str] = []
    if dealer_catalog.get("schema_version") != 1 or dealer_catalog.get("market") != "PT":
        errors.append("catálogo de concessionários tem de usar schema 1 e mercado PT")
    if dealer_catalog.get("reference_location") != "São Mamede de Infesta, Matosinhos":
        errors.append("referência dos concessionários tem de ser São Mamede de Infesta")
    active_brands = {model["brand"] for model in catalog["models"]}
    dealers = dealer_catalog.get("dealers", [])
    dealer_brands = [dealer.get("brand") for dealer in dealers]
    missing = active_brands - set(dealer_brands)
    extra = set(dealer_brands) - active_brands
    if missing:
        errors.append(f"marcas sem concessionário próximo: {sorted(missing)}")
    if extra:
        errors.append(f"concessionários sem marca ativa: {sorted(extra)}")
    if len(dealer_brands) != len(set(dealer_brands)):
        errors.append("cada marca tem de ter exatamente um concessionário preferencial")
    for dealer in dealers:
        label = f"Concessionário {dealer.get('brand', '?')}"
        missing_fields = DEALER_REQUIRED - dealer.keys()
        if missing_fields:
            errors.append(f"{label}: campos em falta: {sorted(missing_fields)}")
        for field in ("brand", "name", "address", "postal_code", "locality", "phone"):
            if not isinstance(dealer.get(field), str) or not dealer[field].strip():
                errors.append(f"{label}: {field} vazio")
        for field in ("official_url", "maps_url"):
            parsed = urlparse(dealer.get(field, ""))
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{label}: {field} não é URL HTTPS")
        try:
            dt.date.fromisoformat(dealer.get("verified_on", ""))
        except ValueError:
            errors.append(f"{label}: verified_on inválido")
        if "sales" not in dealer.get("services", []):
            errors.append(f"{label}: tem de vender veículos novos")
    return errors


def check_link(url: str) -> tuple[int | None, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CarroLiliana/2.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.geturl()
    except urllib.error.HTTPError as error:
        return error.code, error.geturl()
    except TimeoutError as error:
        # mini.pt e ford.pt nao respondem a urllib mas abrem no browser. Igual ao
        # update_catalog: bloqueio (408), nao link partido. DNS/ligacao recusada
        # continuam a falhar, porque ai o link esta mesmo morto.
        return 408, str(error)
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            return 408, str(error)
        return None, str(error)


def interleave_by_host(urls: list[str]) -> list[str]:
    """Alternar entre dominios para nao lancar pedidos simultaneos ao mesmo host.

    Por ordem alfabetica as 5 URLs da citroen.pt ficam adjacentes e seriam
    pedidas ao mesmo tempo, o que provoca HTTP 429. Alternar por dominio mantem
    o paralelismo mas distribui a carga.
    """
    by_host: dict[str, list[str]] = {}
    for url in urls:
        by_host.setdefault(urlparse(url).netloc, []).append(url)
    queues = [sorted(group) for _, group in sorted(by_host.items())]
    schedule: list[str] = []
    for index in range(max((len(group) for group in queues), default=0)):
        schedule.extend(group[index] for group in queues if index < len(group))
    return schedule


def check_links(urls: list[str], workers: int = LINK_WORKERS) -> list[tuple[str, int | None, str]]:
    """Verificar as ligacoes em paralelo, devolvendo os resultados por ordem de URL.

    A ordem de execucao alterna entre dominios, mas a ordem de saida e sempre
    alfabetica para o relatorio ser diffavel entre execucoes, independentemente
    de qual thread terminou primeiro.
    """
    schedule = interleave_by_host(urls)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        outcomes = dict(zip(schedule, pool.map(check_link, schedule), strict=True))
    return [(url, *outcomes[url]) for url in sorted(urls)]


def image_budget_warnings(catalog: dict, *, detailed: bool = False) -> list[str]:
    """Achados de peso das fotografias, separados dos erros de validacao.

    Uma fotografia pesada e um problema de desempenho, nao de correcao: o
    catalogo continua valido. Sai como AVISO e so faz falhar com --check-budgets.

    Por omissao devolve um resumo de uma linha, para nao afogar os avisos de
    frescura em cada `make validate`. Com detailed=True lista cada fotografia.
    """
    oversized: list[tuple[int, str]] = []
    total = 0
    for model in catalog.get("models", []):
        image = ROOT / "web" / model.get("image_path", "")
        if not image.is_file():
            continue
        size = image.stat().st_size
        total += size
        if size > MAX_IMAGE_BYTES:
            oversized.append((size, f"{model.get('brand', '?')} {model.get('model', '?')}"))
    oversized.sort(reverse=True)

    notes: list[str] = []
    limit_kb = MAX_IMAGE_BYTES / 1000
    if detailed:
        notes.extend(f"{label}: fotografia com {size / 1000:.0f} KB excede o orçamento de {limit_kb:.0f} KB" for size, label in oversized)
    elif oversized:
        worst = ", ".join(f"{label} {size / 1000:.0f} KB" for size, label in oversized[:3])
        notes.append(f"{len(oversized)} fotografia(s) excedem {limit_kb:.0f} KB (piores: {worst})")
    if total > MAX_IMAGE_TOTAL_BYTES:
        notes.append(f"fotografias somam {total / 1e6:.1f} MB e excedem o orçamento total de {MAX_IMAGE_TOTAL_BYTES / 1e6:.0f} MB")
    return notes


def _older_than_max_age(value: str | None) -> bool:
    try:
        return (TODAY - dt.date.fromisoformat(value or "")).days > MAX_AGE_DAYS
    except ValueError:
        return False


def staleness_warnings(catalog: dict, dealer_catalog: dict) -> list[str]:
    """Achados que aparecem apenas porque o tempo passou.

    Ficam fora de validate_catalog/validate_dealers de proposito: caso contrario
    o catalogo deixaria de compilar sozinho ao fim de MAX_AGE_DAYS e a suite de
    testes passaria a falhar por efeito do calendario, nao por regressao.
    """
    notes: list[str] = []
    for source in catalog.get("discovery_sources", []):
        if _older_than_max_age(source.get("verified_on")):
            notes.append(f"Fonte de descoberta {source.get('name', '?')}: verificação tem mais de {MAX_AGE_DAYS} dias")
    for model in catalog.get("models", []):
        label = f"{model.get('brand', '?')} {model.get('model', '?')}"
        if _older_than_max_age(model.get("last_verified")):
            notes.append(f"{label}: verificação tem mais de {MAX_AGE_DAYS} dias")
        for variant in model.get("variants", []):
            pricing = variant.get("pricing", {})
            offers = pricing.get("offers", []) if isinstance(pricing, dict) else []
            for offer in offers:
                if not isinstance(offer, dict) or offer.get("kind") != "campaign_price":
                    continue
                validity = offer.get("validity")
                expiry = validity.get("valid_until") if isinstance(validity, dict) else None
                if not expiry:
                    continue
                try:
                    if dt.date.fromisoformat(expiry) < TODAY:
                        notes.append(f"{label} / {variant.get('name', '?')}: campanha expirada em {expiry}")
                except ValueError:
                    continue
    for dealer in dealer_catalog.get("dealers", []):
        if _older_than_max_age(dealer.get("verified_on")):
            notes.append(f"Concessionário {dealer.get('brand', '?')}: verificação tem mais de {MAX_AGE_DAYS} dias")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-links", action="store_true", help="Verify every unique official HTTP source")
    parser.add_argument(
        "--link-workers",
        type=int,
        default=LINK_WORKERS,
        help=f"quantas ligações verificar em paralelo (predefinição: {LINK_WORKERS})",
    )
    parser.add_argument(
        "--check-budgets",
        action="store_true",
        help="Tratar fotografias acima do orçamento de peso como erro",
    )
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Tratar verificações com mais de 45 dias e campanhas expiradas como erro",
    )
    parser.add_argument("--run-tests", action="store_true", help="Executar suíte de testes unitários em tests/")
    args = parser.parse_args()
    if args.run_tests:
        import subprocess
        import unittest

        enrich_script = ROOT / "scripts" / "enrich_pros_cons.py"
        if enrich_script.exists():
            enrich_script.unlink()
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        runner = unittest.TextTestRunner(verbosity=2)
        py_result = runner.run(suite)
        js_files = [str(p) for p in (ROOT / "tests").glob("*.test.js")]
        js_code = 0
        if js_files:
            print("\nExecuting Node JS tests:")
            proc = subprocess.run(["node", "--test", *sorted(js_files)])
            js_code = proc.returncode
        return 0 if (py_result.wasSuccessful() and js_code == 0) else 1
    catalog = load_catalog()
    errors = validate_catalog(catalog)
    errors.extend(duplicate_image_errors(catalog))
    dealer_catalog = load_dealers()
    errors.extend(validate_dealers(catalog, dealer_catalog))
    stale = staleness_warnings(catalog, dealer_catalog)
    if stale and args.check_freshness:
        errors.extend(stale)
    elif stale:
        print("\n".join(f"AVISO: {note}" for note in stale))
    budgets = image_budget_warnings(catalog, detailed=args.check_budgets)
    if budgets and args.check_budgets:
        errors.extend(budgets)
    elif budgets:
        print("\n".join(f"AVISO: {note}" for note in budgets))
    if args.check_links:
        links = {source["url"] for model in vehicle_records() for source in model["data_sources"]}
        links.update(source["url"] for source in catalog["discovery_sources"])
        links.update(dealer["official_url"] for dealer in dealer_catalog["dealers"])
        blocked: list[str] = []
        verified = 0
        for url, status, destination in check_links(sorted(links), args.link_workers):
            print(f"{status or 'ERRO'}  {url} -> {destination}")
            if status in VERIFIED_LINK_CODES:
                verified += 1
            elif status in BLOCKED_LINK_CODES:
                blocked.append(f"{url} (HTTP {status})")
            else:
                errors.append(f"fonte devolveu {status}: {url} -> {destination}")
        # Um resumo verde sem esta contagem esconde que uma parte das fontes
        # respondeu com anti-bot e por isso nao foi realmente verificada.
        print(f"\nLIGAÇÕES: {len(links)} no total, {verified} verificadas, {len(blocked)} não verificadas, {len(links) - verified - len(blocked)} quebradas")
        if blocked:
            print(f"REVER MANUALMENTE NO BROWSER: {len(blocked)} fonte(s) responderam com proteção anti-bot ou sem resposta a urllib. A ligação não está quebrada, mas o conteúdo NÃO foi verificado:")
            print("\n".join(f"  {item}" for item in blocked))
    if errors:
        print("\n".join(f"ERRO: {error}" for error in errors))
        return 1
    variants = sum(len(model["variants"]) for model in catalog["models"])
    print(f"OK: {len(catalog['models'])} modelos / {variants} variantes BEV válidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

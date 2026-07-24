"""Validate the canonical PT BEV catalogue, local images, and source links."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from compile_data import ROOT, load_catalog, load_dealers, vehicle_records

TODAY = dt.date.today()
MAX_PRICE = 40_000
MAX_AGE_DAYS = 45
VALID_LINK_CODES = {200, 301, 302, 403, 429}
MODEL_REQUIRED = {"brand", "model", "powertrain", "segment", "availability_status", "eligible", "official_link", "image_path", "last_verified", "data_sources", "variants"}
VARIANT_REQUIRED = {"name", "battery_capacity_kwh", "wltp_range_combined_km", "power_kw", "power_hp", "pricing"}
DEALER_REQUIRED = {"brand", "name", "address", "postal_code", "locality", "phone", "email", "official_url", "maps_url", "services", "verified_on"}
DISCOVERY_REQUIRED = {"name", "url", "type", "verified_on", "usage_policy", "known_limitations"}


def effective_price(pricing: dict) -> float | None:
    return pricing.get("particular_campaign_price_vat_incl") or pricing.get("particular_list_price_vat_incl")


def validate_catalog(catalog: dict) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != 2:
        errors.append("schema_version tem de ser 2")
    if catalog.get("market") != "PT" or catalog.get("currency") != "EUR":
        errors.append("catálogo tem de usar mercado PT e moeda EUR")
    scope = catalog.get("scope", {})
    if (
        scope.get("powertrain") != "BEV"
        or scope.get("vehicle_type") != "M1 passenger car"
        or scope.get("condition") != "new"
        or scope.get("maximum_vat_inclusive_price_eur") != MAX_PRICE
    ):
        errors.append("scope tem de ser M1, novo, exclusivamente BEV e limitado a 40.000 €")
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
                verified = dt.date.fromisoformat(source.get("verified_on", ""))
                if (TODAY - verified).days > MAX_AGE_DAYS:
                    errors.append(f"{label}: verificação tem mais de {MAX_AGE_DAYS} dias")
            except ValueError:
                errors.append(f"{label}: verified_on inválido")
            if not isinstance(source.get("known_limitations"), list) or not source["known_limitations"]:
                errors.append(f"{label}: limitações não documentadas")
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        return errors + ["models tem de ser uma lista não vazia"]

    seen: set[tuple[str, str]] = set()
    for model in models:
        label = f"{model.get('brand', '?')} {model.get('model', '?')}"
        missing = MODEL_REQUIRED - model.keys()
        if missing:
            errors.append(f"{label}: campos em falta: {sorted(missing)}")
        key = (model.get("brand", ""), model.get("model", ""))
        if key in seen:
            errors.append(f"{label}: modelo duplicado")
        seen.add(key)
        if model.get("powertrain") != "BEV":
            errors.append(f"{label}: powertrain não é BEV")
        if model.get("availability_status") != "available" or model.get("eligible") is not True:
            errors.append(f"{label}: modelo não está disponível/elegível")
        try:
            verified = dt.date.fromisoformat(model.get("last_verified", ""))
            if (TODAY - verified).days > MAX_AGE_DAYS:
                errors.append(f"{label}: verificação tem mais de {MAX_AGE_DAYS} dias")
        except ValueError:
            errors.append(f"{label}: last_verified inválido")
        for field in ("official_link",):
            parsed = urlparse(model.get(field, ""))
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"{label}: {field} não é URL HTTPS")
        image = ROOT / "web" / model.get("image_path", "")
        if not model.get("image_path") or not image.is_file() or image.stat().st_size < 5_000:
            errors.append(f"{label}: imagem local ausente ou inválida ({model.get('image_path')!r})")
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
        variants = model.get("variants")
        if not isinstance(variants, list) or not variants:
            errors.append(f"{label}: variants vazio")
            continue
        variant_names: set[str] = set()
        for variant in variants:
            vlabel = f"{label} / {variant.get('name', '?')}"
            missing = VARIANT_REQUIRED - variant.keys()
            if missing:
                errors.append(f"{vlabel}: campos em falta: {sorted(missing)}")
            if variant.get("name") in variant_names:
                errors.append(f"{vlabel}: variante duplicada")
            variant_names.add(variant.get("name"))
            for numeric in ("battery_capacity_kwh", "wltp_range_combined_km", "power_kw", "power_hp"):
                if not isinstance(variant.get(numeric), (int, float)) or variant.get(numeric, 0) <= 0:
                    errors.append(f"{vlabel}: {numeric} inválido")
            pricing = variant.get("pricing", {})
            price = effective_price(pricing)
            if not isinstance(price, (int, float)) or price <= 0 or price > MAX_PRICE:
                errors.append(f"{vlabel}: preço elegível inválido/acima de 40.000 € ({price})")
            if pricing.get("particular_campaign_price_vat_incl") and not str(
                pricing.get("campaign_conditions") or ""
            ).strip():
                errors.append(f"{vlabel}: campanha sem condições explícitas")
            expiry = pricing.get("campaign_valid_until")
            if pricing.get("particular_campaign_price_vat_incl") and expiry:
                try:
                    if dt.date.fromisoformat(expiry) < TODAY:
                        errors.append(f"{vlabel}: campanha expirada em {expiry}")
                except ValueError:
                    errors.append(f"{vlabel}: campaign_valid_until inválido")
    return errors


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
            verified = dt.date.fromisoformat(dealer.get("verified_on", ""))
            if (TODAY - verified).days > MAX_AGE_DAYS:
                errors.append(f"{label}: verificação tem mais de {MAX_AGE_DAYS} dias")
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
    except (urllib.error.URLError, TimeoutError) as error:
        return None, str(error)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-links", action="store_true", help="Verify every unique official HTTP source")
    args = parser.parse_args()
    catalog = load_catalog()
    errors = validate_catalog(catalog)
    dealer_catalog = load_dealers()
    errors.extend(validate_dealers(catalog, dealer_catalog))
    if args.check_links:
        links = {source["url"] for model in vehicle_records() for source in model["data_sources"]}
        links.update(source["url"] for source in catalog["discovery_sources"])
        links.update(dealer["official_url"] for dealer in dealer_catalog["dealers"])
        for url in sorted(links):
            status, destination = check_link(url)
            print(f"{status or 'ERRO'}  {url} -> {destination}")
            if status not in VALID_LINK_CODES:
                errors.append(f"fonte devolveu {status}: {url} -> {destination}")
    if errors:
        print("\n".join(f"ERRO: {error}" for error in errors))
        return 1
    variants = sum(len(model["variants"]) for model in catalog["models"])
    print(f"OK: {len(catalog['models'])} modelos / {variants} variantes BEV válidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

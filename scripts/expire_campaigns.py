#!/usr/bin/env python3
"""Recalcular elegibilidade v3 sem apagar ofertas de referência.

Uma oferta expirada deixa de contar como confirmada atual, mas permanece no
registo para não transformar histórico ou preço de referência em ausência de
dados. Variantes com ofertas ``reference`` sobrevivem como
``potential_reference``; só variantes sem qualquer base de preço atual são
removidas.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from rules import effective_confirmed_offer, iso_date, variant_eligibility_tier

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
DEALERS_PATH = ROOT / "data" / "dealers" / "near_sao_mamede.json"


def today() -> dt.date:
    return dt.datetime.now(tz=ZoneInfo("Europe/Lisbon")).date()


def effective_price(pricing: dict, reference: dt.date | None = None) -> float | None:
    variant = {"pricing": pricing}
    offer = effective_confirmed_offer(variant, reference or today())
    return offer.get("amount_eur") if offer else None


def expired_campaigns(pricing: dict, reference: dt.date) -> list[dict]:
    offers = pricing.get("offers", []) if isinstance(pricing, dict) else []
    return [
        offer
        for offer in offers
        if isinstance(offer, dict)
        and offer.get("kind") == "campaign_price"
        and isinstance(offer.get("validity"), dict)
        and offer["validity"].get("valid_until")
        and (expiry := iso_date(offer["validity"]["valid_until"])) is not None
        and expiry < reference
    ]


def is_expired(pricing: dict, reference: dt.date) -> bool:
    """Compatibilidade de API: existe campanha v3 com validade já passada."""
    return bool(expired_campaigns(pricing, reference))


def expire_catalog(catalog: dict, dealer_catalog: dict, reference: dt.date) -> list[str]:
    report: list[str] = []
    surviving_models: list[dict] = []

    for model in catalog.get("models", []):
        label = f"{model.get('brand', '?')} {model.get('model', '?')}"
        surviving_variants: list[dict] = []
        for variant in model.get("variants", []):
            vlabel = f"{label} / {variant.get('name', '?')}"
            pricing = variant.get("pricing", {})
            for offer in expired_campaigns(pricing, reference):
                report.append(
                    f"OFERTA EXPIRADA    {vlabel}: {offer.get('amount_eur')} € válida até "
                    f"{offer.get('validity', {}).get('valid_until')} excluída da elegibilidade confirmada"
                )

            tier = variant_eligibility_tier(variant, reference)
            variant["eligibility_status"] = tier
            variant["eligibility_tier"] = tier
            if tier == "not_demonstrated":
                report.append(f"VARIANTE REMOVIDA  {vlabel}: sem oferta atual ou referência conservável")
                continue
            surviving_variants.append(variant)

        if not surviving_variants:
            report.append(f"MODELO REMOVIDO    {label}: ficou sem variantes demonstráveis")
            continue
        model["variants"] = surviving_variants
        model_tier = "confirmed_eligible" if any(item.get("eligibility_tier") == "confirmed_eligible" for item in surviving_variants) else "potential_reference" if any(
            item.get("eligibility_tier") == "potential_reference" for item in surviving_variants
        ) else "not_demonstrated"
        model["eligibility_status"] = model_tier
        model["eligibility_tier"] = model_tier
        model["eligibility_reason"] = {
            "confirmed_eligible": "Existe oferta confirmada atual dentro do limite.",
            "potential_reference": "Existem apenas ofertas de referência ou ofertas confirmadas expiradas.",
            "not_demonstrated": "Não existe oferta atual demonstrável.",
        }[model_tier]
        surviving_models.append(model)

    catalog["models"] = surviving_models
    active_brands = {model["brand"] for model in surviving_models}
    surviving_dealers: list[dict] = []
    for dealer in dealer_catalog.get("dealers", []):
        if dealer.get("brand") in active_brands:
            surviving_dealers.append(dealer)
        else:
            report.append(f"STAND REMOVIDO     {dealer.get('brand', '?')}: a marca deixou de ter modelos no catálogo")
    dealer_catalog["dealers"] = surviving_dealers
    return report


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escrever alterações v3 nos JSON canónicos")
    parser.add_argument("--date", help="data de referência ISO (por omissão, hoje em Lisboa)")
    args = parser.parse_args()
    reference = dt.date.fromisoformat(args.date) if args.date else today()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    dealer_catalog = json.loads(DEALERS_PATH.read_text(encoding="utf-8"))
    report = expire_catalog(catalog, dealer_catalog, reference)
    if not report:
        print(f"Nenhuma oferta expirada em {reference}.")
        return 0
    print("\n".join(report))
    if not args.apply:
        print(f"\n{len(report)} alteração(ões) pendentes; nada foi escrito. Repetir com --apply.")
        return 0
    write_json(CATALOG_PATH, catalog)
    write_json(DEALERS_PATH, dealer_catalog)
    variants = sum(len(model["variants"]) for model in catalog["models"])
    print(f"\nAplicado: {len(catalog['models'])} modelos / {variants} variantes / {len(dealer_catalog['dealers'])} concessionários.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

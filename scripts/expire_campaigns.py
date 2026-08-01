#!/usr/bin/env python3
"""Remover do catálogo as campanhas cuja validade já passou, e o que deixa de ser elegível.

Uma campanha expirada não é um aviso: é informação errada no portal. Quem abre a
aplicação vê um preço que já ninguém pratica. Este passo apaga o preço de
campanha, as condições e a validade, e depois deixa o catálogo cair para o PVP.

A queda tem consequências em cascata, todas na secção 6 do AGENTS.md:

- se a variante ficar sem preço elegível até ao limite, deixa de ser elegível e
  sai do catálogo (regra 6.10);
- se o modelo ficar sem variantes, sai também (regra 6.11);
- se a marca ficar sem modelos, o concessionário preferencial dessa marca sai
  (regra 9), porque o conjunto de marcas tem de ser igual dos dois lados.

Nada é adivinhado: a única coisa que este script decide é que uma data que já
passou, passou. Se a marca publicou entretanto uma campanha nova, ela volta a
entrar pela revisão humana das fontes — não por omissão deste passo.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
DEALERS_PATH = ROOT / "data" / "dealers" / "near_sao_mamede.json"
MAX_PRICE = 40_000
CAMPAIGN_FIELDS = (
    "particular_campaign_price_vat_incl",
    "campaign_conditions",
    "campaign_valid_until",
)


def today() -> dt.date:
    return dt.datetime.now(tz=ZoneInfo("Europe/Lisbon")).date()


def effective_price(pricing: dict) -> float | None:
    return pricing.get("particular_campaign_price_vat_incl") or pricing.get("particular_list_price_vat_incl")


def is_expired(pricing: dict, reference: dt.date) -> bool:
    """Uma campanha só expira se tiver preço de campanha E validade já passada.

    Sem validade publicada o catálogo guarda `null` (AGENTS.md secção 8) e a
    campanha não pode ser declarada expirada — tem de ser confirmada na fonte.
    """
    if not pricing.get("particular_campaign_price_vat_incl"):
        return False
    expiry = pricing.get("campaign_valid_until")
    if not expiry:
        return False
    try:
        return dt.date.fromisoformat(expiry) < reference
    except (TypeError, ValueError):
        return False


def expire_catalog(catalog: dict, dealer_catalog: dict, reference: dt.date) -> list[str]:
    """Aplicar a cascata no sítio e devolver o relatório do que mudou."""
    report: list[str] = []
    surviving_models = []

    for model in catalog.get("models", []):
        label = f"{model.get('brand', '?')} {model.get('model', '?')}"
        surviving_variants = []

        for variant in model.get("variants", []):
            vlabel = f"{label} / {variant.get('name', '?')}"
            pricing = variant.get("pricing", {})

            if is_expired(pricing, reference):
                expired_price = pricing["particular_campaign_price_vat_incl"]
                expiry = pricing["campaign_valid_until"]
                for field in CAMPAIGN_FIELDS:
                    pricing[field] = None
                report.append(f"CAMPANHA EXPIRADA  {vlabel}: {expired_price} € válida até {expiry} removida")

            price = effective_price(pricing)
            if not isinstance(price, (int, float)) or price <= 0:
                report.append(f"VARIANTE REMOVIDA  {vlabel}: ficou sem preço elegível")
                continue
            if price > MAX_PRICE:
                report.append(f"VARIANTE REMOVIDA  {vlabel}: PVP {price} € excede o limite de {MAX_PRICE} €")
                continue
            surviving_variants.append(variant)

        if not surviving_variants:
            report.append(f"MODELO REMOVIDO    {label}: ficou sem variantes elegíveis")
            continue
        model["variants"] = surviving_variants
        surviving_models.append(model)

    catalog["models"] = surviving_models

    active_brands = {model["brand"] for model in surviving_models}
    surviving_dealers = []
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
    parser.add_argument("--apply", action="store_true", help="escrever as alterações nos JSON canónicos")
    parser.add_argument("--date", help="data de referência ISO (por omissão, hoje em Lisboa)")
    args = parser.parse_args()

    reference = dt.date.fromisoformat(args.date) if args.date else today()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    dealer_catalog = json.loads(DEALERS_PATH.read_text(encoding="utf-8"))

    report = expire_catalog(catalog, dealer_catalog, reference)
    if not report:
        print(f"Nenhuma campanha expirada em {reference}.")
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

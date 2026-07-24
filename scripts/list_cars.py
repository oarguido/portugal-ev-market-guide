"""Print a compact summary of the canonical catalogue."""

from compile_data import vehicle_records


def effective_price(pricing: dict) -> float | None:
    return pricing.get("particular_campaign_price_vat_incl") or pricing.get("particular_list_price_vat_incl")


def main() -> None:
    print(f"{'MARCA / MODELO':<34} {'VERSÃO':<28} {'WLTP':>7} {'PREÇO':>13}  VERIFICADO")
    print("-" * 105)
    for model in vehicle_records():
        for variant in model["variants"]:
            price = effective_price(variant["pricing"])
            print(
                f"{model['brand']} {model['model']:<{33-len(model['brand'])}} "
                f"{variant['name']:<28} {variant['wltp_range_combined_km']:>4} km "
                f"{price:>10,.2f} €  {model['last_verified']}"
            )


if __name__ == "__main__":
    main()

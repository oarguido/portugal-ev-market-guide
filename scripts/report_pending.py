#!/usr/bin/env python3
"""Dizer, no fim de uma atualização, exatamente o que falta fazer à mão.

`make atualizar` faz tudo o que um script pode fazer sozinho. O que sobra não
sobra por preguiça: confirmar um preço numa página protegida contra robôs,
decidir se um lançamento é M1 e está mesmo encomendável em Portugal, ou olhar
para uma fotografia e reconhecer o carro — nada disso é automatizável, e a
secção 15 do AGENTS.md diz-lo desde o início.

O que era evitável era acabar a atualização sem saber o que ficou por fazer.
Este relatório fecha essa lacuna: em vez de "correu bem", diz quais são as
páginas por abrir, as campanhas prestes a expirar e as verificações a envelhecer.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from rules import MAX_AGE_DAYS

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
DEALERS_PATH = ROOT / "data" / "dealers" / "near_sao_mamede.json"
SNAPSHOTS_PATH = ROOT / "data" / "source_snapshots.json"
TODAY = dt.datetime.now(tz=ZoneInfo("Europe/Lisbon")).date()
EXPIRING_SOON_DAYS = 30
BLOCKED_STATUS = {403, 408, 429}
STALE_SNAPSHOT_HINT = (
    "Estes snapshots trazem só um código HTTP, sem conteúdo. Se forem muitos, o "
    "ficheiro é anterior ao browser fallback: correr `python3 scripts/update_catalog.py` "
    "volta a lê-los e a lista encolhe."
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def days_until(value: str | None) -> int | None:
    try:
        return (dt.date.fromisoformat(value or "") - TODAY).days
    except ValueError:
        return None


def build_sections(catalog: dict, dealers: dict, snapshots: dict) -> list[tuple[str, list[str]]]:
    expiring: list[str] = []
    undated: list[str] = []
    ageing: list[str] = []

    for model in catalog.get("models", []):
        label = f"{model.get('brand', '?')} {model.get('model', '?')}"
        remaining = days_until(model.get("last_verified"))
        if remaining is not None and -remaining > MAX_AGE_DAYS - 10:
            ageing.append(f"{label}: verificado há {-remaining} dias")
        for variant in model.get("variants", []):
            pricing = variant.get("pricing", {})
            if not pricing.get("particular_campaign_price_vat_incl"):
                continue
            vlabel = f"{label} / {variant.get('name', '?')}"
            expiry = pricing.get("campaign_valid_until")
            if not expiry:
                undated.append(f"{vlabel}: campanha ativa sem validade publicada")
                continue
            left = days_until(expiry)
            if left is not None and 0 <= left <= EXPIRING_SOON_DAYS:
                expiring.append(f"{vlabel}: campanha expira em {expiry} (faltam {left} dias)")

    for dealer in dealers.get("dealers", []):
        remaining = days_until(dealer.get("verified_on"))
        if remaining is not None and -remaining > MAX_AGE_DAYS - 10:
            ageing.append(f"Concessionário {dealer.get('brand', '?')}: verificado há {-remaining} dias")

    # Só as fontes que o catálogo ainda usa: o histórico de snapshots guarda URLs
    # de modelos entretanto removidos, e mandar rever a campanha de um carro que
    # já não está publicado é mandar fazer trabalho inútil.
    live = {source["url"] for model in catalog.get("models", []) for source in model.get("data_sources", [])}
    live.update(source["url"] for source in catalog.get("discovery_sources", []))
    live.update(dealer["official_url"] for dealer in dealers.get("dealers", []) if dealer.get("official_url"))
    blocked = sorted(url for url, snapshot in snapshots.items() if snapshot.get("http_status") in BLOCKED_STATUS and url in live)

    return [
        (
            "CAMPANHAS A EXPIRAR — renovar ou deixar cair antes de a data passar",
            sorted(expiring),
        ),
        (
            "CAMPANHAS SEM VALIDADE PUBLICADA — confirmar na fonte; sem data não expiram sozinhas",
            sorted(undated),
        ),
        (
            "FONTES AINDA POR LER — nem o urllib nem o browser trouxeram conteúdo",
            blocked,
        ),
        (
            f"VERIFICAÇÕES A ENVELHECER — reabrir as fontes antes dos {MAX_AGE_DAYS} dias",
            sorted(ageing),
        ),
    ]


def main() -> int:
    catalog = load(CATALOG_PATH)
    dealers = load(DEALERS_PATH)
    snapshots = load(SNAPSHOTS_PATH)
    sections = build_sections(catalog, dealers, snapshots)

    print("\n" + "═" * 78)
    print(f"POR FAZER À MÃO — {TODAY}")
    print("═" * 78)

    total = 0
    for title, items in sections:
        if not items:
            continue
        total += len(items)
        print(f"\n{title}")
        for item in items:
            print(f"  - {item}")
        if title.startswith("FONTES AINDA POR LER"):
            print(f"    {STALE_SNAPSHOT_HINT}")

    print(
        "\nOs radares de mercado e a leitura de preços já correm sozinhos num browser\n"
        "(`discover_models.py` e `refresh_prices.py`). O que continua a exigir uma\n"
        "pessoa é a decisão: se um candidato é M1, se está mesmo encomendável em\n"
        "Portugal, e se a fotografia mostra o carro certo. Ver AGENTS.md secções 5B,\n"
        "7 e 15. Nenhum preço entra no catálogo sem fonte oficial portuguesa."
    )
    if total:
        print(f"\n{total} ponto(s) à espera de uma pessoa.")
    else:
        print("\nNada pendente do lado automático.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

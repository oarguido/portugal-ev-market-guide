"""Compile the canonical Portuguese BEV catalogue for the offline web app."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
DEALERS_PATH = ROOT / "data" / "dealers" / "near_sao_mamede.json"
BUNDLE_PATH = ROOT / "web" / "assets" / "js" / "car_data.js"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def vehicle_records() -> list[dict]:
    return load_catalog()["models"]


def load_dealers() -> dict:
    return json.loads(DEALERS_PATH.read_text(encoding="utf-8"))


def compile_data() -> None:
    models = vehicle_records()
    dealers = {dealer["brand"]: dealer for dealer in load_dealers()["dealers"]}
    output = "// Gerado automaticamente por scripts/compile_data.py; não editar.\n"
    output += "const CAR_DATA = " + json.dumps(models, indent=2, ensure_ascii=False) + ";\n"
    output += "const DEALER_DATA = " + json.dumps(dealers, indent=2, ensure_ascii=False) + ";\n"
    BUNDLE_PATH.write_text(output, encoding="utf-8")
    variants = sum(len(model["variants"]) for model in models)
    print(f"Compilados {len(models)} modelos / {variants} variantes em {BUNDLE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    compile_data()

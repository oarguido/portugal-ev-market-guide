"""Compile the canonical Portuguese BEV catalogue for the offline web app."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
DEALERS_PATH = ROOT / "data" / "dealers" / "near_sao_mamede.json"
BUNDLE_PATH = ROOT / "web" / "assets" / "js" / "car_data.js"
INDEX_PATH = ROOT / "web" / "index.html"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def vehicle_records() -> list[dict]:
    return load_catalog()["models"]


def load_dealers() -> dict:
    return json.loads(DEALERS_PATH.read_text(encoding="utf-8"))


def stamp_index(bundle: str) -> bool:
    """Carimbar o index.html com a impressão digital do bundle.

    Sem isto, o browser guarda o car_data.js antigo: a resposta traz
    Last-Modified e nenhum Cache-Control, o que autoriza cache heurística. Depois
    de uma atualização que muda `image_path` e arquiva as fotografias antigas, a
    página fica a pedir ficheiros que já não existem — fotografias em branco e
    lista de carros desatualizada, sem nada a indicar porquê. Um simples recarregar
    não chega, porque o pedido nem sai.

    A versão vai no atributo src em vez de ser um cabeçalho, para funcionar também
    quando se abre o web/index.html diretamente do disco, sem servidor nenhum.
    """
    version = hashlib.sha256(bundle.encode("utf-8")).hexdigest()[:12]
    html = INDEX_PATH.read_text(encoding="utf-8")
    updated = re.sub(
        r'(<script src="assets/js/car_data\.js)(\?v=[0-9a-f]+)?(")',
        rf'\1?v={version}\3',
        html,
    )
    if updated == html:
        return False
    INDEX_PATH.write_text(updated, encoding="utf-8")
    return True


def compile_data() -> None:
    catalog = load_catalog()
    dealer_catalog = load_dealers()
    # Fail closed before touching bundle or index. A stale generated bundle is
    # safer than publishing a v2/invalid catalogue as if it were v3.
    from validate_data import duplicate_image_errors, validate_catalog, validate_dealers

    errors = validate_catalog(catalog)
    errors.extend(duplicate_image_errors(catalog))
    errors.extend(validate_dealers(catalog, dealer_catalog))
    if errors:
        rendered = "\n".join(f"ERRO: {error}" for error in errors)
        raise ValueError(f"catálogo recusado; bundle não foi escrito:\n{rendered}")

    models = catalog["models"]
    dealers = {dealer["brand"]: dealer for dealer in dealer_catalog["dealers"]}
    output = "// Gerado automaticamente por scripts/compile_data.py; não editar.\n"
    output += "const CAR_DATA = " + json.dumps(models, indent=2, ensure_ascii=False) + ";\n"
    output += "const DEALER_DATA = " + json.dumps(dealers, indent=2, ensure_ascii=False) + ";\n"
    # Reescrever com conteudo identico so churna o mtime e suja o watch/graph.
    if not BUNDLE_PATH.exists() or BUNDLE_PATH.read_text(encoding="utf-8") != output:
        BUNDLE_PATH.write_text(output, encoding="utf-8")
    if stamp_index(output):
        print("index.html: versão do bundle atualizada")
    variants = sum(len(model["variants"]) for model in models)
    try:
        location = BUNDLE_PATH.relative_to(ROOT)
    except ValueError:
        location = BUNDLE_PATH
    print(f"Compilados {len(models)} modelos / {variants} variantes em {location}")


if __name__ == "__main__":
    compile_data()

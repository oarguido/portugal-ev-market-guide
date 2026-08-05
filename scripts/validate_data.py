"""Validate the canonical PT BEV catalogue, local images, and source links."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import urllib.error
import urllib.request
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from compile_data import ROOT, load_catalog, load_dealers, vehicle_records
from rules import MAX_AGE_DAYS, MAX_PRICE_EUR

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
    "powertrain",
    "segment",
    "availability_status",
    "eligible",
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
VARIANT_REQUIRED = {"name", "battery_capacity_kwh", "wltp_range_combined_km", "power_kw", "power_hp", "pricing"}
DEALER_REQUIRED = {"brand", "name", "address", "postal_code", "locality", "phone", "email", "official_url", "maps_url", "services", "verified_on"}
DISCOVERY_REQUIRED = {"name", "url", "type", "verified_on", "usage_policy", "known_limitations"}


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
        or scope.get("maximum_vat_inclusive_price_eur") != MAX_PRICE_EUR
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
                dt.date.fromisoformat(source.get("verified_on", ""))
            except ValueError:
                errors.append(f"{label}: verified_on inválido")
            if not isinstance(source.get("known_limitations"), list) or not source["known_limitations"]:
                errors.append(f"{label}: limitações não documentadas")
    models = catalog.get("models")
    if not isinstance(models, list) or not models:
        return [*errors, "models tem de ser uma lista não vazia"]

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
            if not isinstance(price, (int, float)) or price <= 0 or price > MAX_PRICE_EUR:
                errors.append(f"{vlabel}: preço elegível inválido/acima de 40.000 € ({price})")
            if pricing.get("particular_campaign_price_vat_incl") and not str(
                pricing.get("campaign_conditions") or ""
            ).strip():
                errors.append(f"{vlabel}: campanha sem condições explícitas")
            expiry = pricing.get("campaign_valid_until")
            if pricing.get("particular_campaign_price_vat_incl") and expiry:
                try:
                    dt.date.fromisoformat(expiry)
                except ValueError:
                    errors.append(f"{vlabel}: campaign_valid_until inválido")
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
    return [
        f"fotografia repetida em modelos diferentes: {', '.join(sorted(nomes))}"
        for nomes in digests.values()
        if len(nomes) > 1
    ]


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
            expiry = pricing.get("campaign_valid_until")
            if not pricing.get("particular_campaign_price_vat_incl") or not expiry:
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
        print(
            f"\nLIGAÇÕES: {len(links)} no total, {verified} verificadas, "
            f"{len(blocked)} não verificadas, {len(links) - verified - len(blocked)} quebradas"
        )
        if blocked:
            print(
                f"REVER MANUALMENTE NO BROWSER: {len(blocked)} fonte(s) responderam com proteção "
                "anti-bot ou sem resposta a urllib. A ligação não está quebrada, mas o conteúdo "
                "NÃO foi verificado:"
            )
            print("\n".join(f"  {item}" for item in blocked))
    if errors:
        print("\n".join(f"ERRO: {error}" for error in errors))
        return 1
    variants = sum(len(model["variants"]) for model in catalog["models"])
    print(f"OK: {len(catalog['models'])} modelos / {variants} variantes BEV válidas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

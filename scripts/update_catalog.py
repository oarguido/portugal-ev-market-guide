"""One-command catalogue refresh gate.

This intentionally never guesses new prices. It downloads every official source,
stores a content fingerprint, reports changed pages for human review, optionally
refreshes official Open Graph photos, then validates and compiles approved JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request
import urllib.error
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from compile_data import ROOT, load_catalog, load_dealers

CACHE = ROOT / "data" / "source_snapshots.json"
HTML_FINGERPRINT_VERSION = "html-visible-text-v1"
BINARY_FINGERPRINT_VERSION = "binary-raw-v1"
FETCH_ATTEMPTS = 3
RETRYABLE_HTTP_CODES = {500, 502, 503, 504}
DYNAMIC_VISIBLE_TEXT = re.compile(r"\bAtualmente\s+(?:aberto|fechado)\b", re.I)
OG_IMAGE = re.compile(r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)
OG_IMAGE_REVERSED = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']', re.I)


class VisibleTextParser(HTMLParser):
    """Extract stable user-visible text while ignoring volatile page machinery."""

    SKIPPED_TAGS = {"script", "style", "noscript", "svg", "template"}
    META_FIELDS = {"description", "og:title", "og:description"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipped_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.SKIPPED_TAGS:
            self.skipped_depth += 1
            return
        if self.skipped_depth or tag != "meta":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        field = (values.get("name") or values.get("property") or "").lower()
        if field in self.META_FIELDS and values.get("content"):
            self.parts.append(values["content"])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIPPED_TAGS and self.skipped_depth:
            self.skipped_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skipped_depth and data.strip():
            self.parts.append(data)


def fetch(url: str, attempts: int = FETCH_ATTEMPTS) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 CarroLilianaCatalog/2.0"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return response.read(), response.geturl()
        except urllib.error.HTTPError as error:
            if error.code not in RETRYABLE_HTTP_CODES or attempt == attempts:
                raise
            print(f"RETRY {attempt}/{attempts}  HTTP {error.code}  {url}")
        except (urllib.error.URLError, TimeoutError):
            if attempt == attempts:
                raise
            print(f"RETRY {attempt}/{attempts}  ligação/timeout  {url}")
        time.sleep(attempt)
    raise RuntimeError(f"fetch sem resultado: {url}")


def normalized_visible_text(body: bytes) -> str:
    parser = VisibleTextParser()
    parser.feed(body.decode("utf-8", errors="ignore"))
    parser.close()
    text = unicodedata.normalize("NFKC", " ".join(parser.parts))
    text = DYNAMIC_VISIBLE_TEXT.sub("", text)
    return " ".join(text.split())


def build_snapshot(
    body: bytes,
    final_url: str,
    *,
    source_type: str | None = None,
) -> dict:
    raw_digest = hashlib.sha256(body).hexdigest()
    is_pdf = body.lstrip().startswith(b"%PDF") or final_url.lower().split("?", 1)[0].endswith(".pdf")
    visible_text = "" if is_pdf else normalized_visible_text(body)

    if visible_text:
        version = HTML_FINGERPRINT_VERSION
        digest = hashlib.sha256(visible_text.encode("utf-8")).hexdigest()
    else:
        version = BINARY_FINGERPRINT_VERSION
        digest = raw_digest

    snapshot = {
        "fingerprint_version": version,
        "sha256": digest,
        "raw_sha256": raw_digest,
        "final_url": final_url,
        "bytes": len(body),
    }
    if visible_text:
        snapshot["normalized_chars"] = len(visible_text)
    if source_type:
        snapshot["source_type"] = source_type
    return snapshot


def blocked_snapshot(
    status: int,
    final_url: str,
    *,
    source_type: str | None = None,
) -> dict:
    snapshot = {"http_status": status, "final_url": final_url, "bytes": 0}
    if source_type:
        snapshot["source_type"] = source_type
    return snapshot


def snapshot_changed(previous: dict | None, current: dict) -> bool:
    if not previous:
        return False

    previous_status = previous.get("http_status")
    current_status = current.get("http_status")
    if previous_status is not None or current_status is not None:
        if previous_status in {403, 429} and current_status in {403, 429}:
            # Bloqueio nos dois lados nao prova ausencia de alteracao (AGENTS.md).
            # Nao marcamos como alterado, mas o chamador tem de rever no browser.
            return False
        return previous_status != current_status

    if previous.get("fingerprint_version") == current.get("fingerprint_version"):
        return previous.get("sha256") != current.get("sha256")

    # Legacy snapshots used a raw HTML hash. Compare like-for-like until the
    # reviewed baseline is accepted once with the semantic fingerprint format.
    return previous.get("sha256") != current.get("raw_sha256")


def slug(model: dict) -> str:
    value = f"{model['brand']}-{model['model']}".lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def refresh_photo(model: dict, html: bytes, page_url: str) -> bool:
    text = html.decode("utf-8", errors="ignore")
    match = OG_IMAGE.search(text) or OG_IMAGE_REVERSED.search(text)
    if not match:
        return False
    image_url = urljoin(page_url, match.group(1).replace("&amp;", "&"))
    image_data, _ = fetch(image_url)
    if len(image_data) < 5_000:
        return False
    extension = ".png" if image_data.startswith(b"\x89PNG") else ".jpg"
    directory = ROOT / "web" / "assets" / "images" / "vehicles" / slug(model)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"official{extension}"
    target.write_bytes(image_data)
    model["image_path"] = str(target.relative_to(ROOT / "web"))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-photos", action="store_true")
    parser.add_argument("--accept-source-changes", action="store_true", help="Store current fingerprints after reviewing changed official pages")
    args = parser.parse_args()
    catalog = load_catalog()
    dealer_catalog = load_dealers()
    previous = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    current: dict[str, dict] = {}
    changed: list[str] = []
    failed: list[str] = []
    blocked_sources: list[str] = []
    pages: dict[str, tuple[bytes, str]] = {}
    processed: set[str] = set()

    def process_source(
        url: str,
        *,
        annotation: str = "",
        source_type: str | None = None,
    ) -> None:
        if url in processed:
            return
        processed.add(url)
        try:
            body, destination = fetch(url)
            pages[url] = (body, destination)
            snapshot = build_snapshot(body, destination, source_type=source_type)
            current[url] = snapshot
            if snapshot_changed(previous.get(url), snapshot):
                changed.append(url)
            print(f"OK {len(body):>8} B  {url}{annotation}")
        except urllib.error.HTTPError as error:
            if error.code in {403, 429}:
                blocked = blocked_snapshot(
                    error.code,
                    error.geturl(),
                    source_type=source_type,
                )
                previous_snapshot = previous.get(url)
                # Anti-bot responses contain no comparable content. Preserve the
                # last successful semantic baseline instead of replacing it with
                # an intermittent 403/429 status.
                snapshot = (
                    dict(previous_snapshot)
                    if previous_snapshot and previous_snapshot.get("sha256")
                    else blocked
                )
                current[url] = snapshot
                if snapshot_changed(previous_snapshot, blocked):
                    changed.append(url)
                blocked_sources.append(f"{url} (HTTP {error.code})")
                print(f"OK {error.code:>8}    {url} (proteção anti-bot; acessível no navegador)")
                return
            failed.append(url)
            print(f"ERRO {url}: HTTP {error.code}")
        except Exception as error:
            failed.append(url)
            print(f"ERRO {url}: {error}")

    for source in catalog.get("discovery_sources", []):
        process_source(
            source["url"],
            annotation=" (radar de mercado secundário)",
            source_type=source["type"],
        )

    for model in catalog["models"]:
        for source in model["data_sources"]:
            process_source(source["url"])

    for dealer in dealer_catalog["dealers"]:
        process_source(
            dealer["official_url"],
            annotation=f" (concessionário {dealer['brand']})",
        )
    if args.refresh_photos:
        for model in catalog["models"]:
            body, final_url = pages.get(model["official_link"], (b"", model["official_link"]))
            if body and refresh_photo(model, body, final_url):
                print(f"FOTO {model['brand']} {model['model']}")
        (ROOT / "data" / "vehicles" / "pt_market.json").write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not failed and (args.accept_source_changes or not CACHE.exists()):
        CACHE.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failed:
        print(f"\nFalha persistente em {len(failed)} fonte(s); nenhuma baseline foi gravada.")
        return 1
    if blocked_sources:
        print(
            f"\nREVER MANUALMENTE NO BROWSER: {len(blocked_sources)} fonte(s) responderam com "
            "proteção anti-bot. Um bloqueio não prova que a página não mudou, por isso "
            "preço, autonomia e campanha destas fontes NÃO foram verificados:"
        )
        print("\n".join(f"  {item}" for item in blocked_sources))
    if changed and not args.accept_source_changes:
        print("\nFontes alteradas; rever os campos associados e voltar a executar com --accept-source-changes:")
        print("\n".join(changed))
        return 2
    commands = [
        [sys.executable, str(ROOT / "scripts" / "validate_data.py")],
        [sys.executable, str(ROOT / "scripts" / "compile_data.py")],
        ["make", "test"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

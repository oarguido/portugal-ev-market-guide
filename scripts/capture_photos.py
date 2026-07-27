"""Capture model-specific images from official pages with a real browser."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urljoin

from compile_data import CATALOG_PATH, ROOT, load_catalog
from update_catalog import fetch


def run(*arguments: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["agent-browser", *arguments], cwd=ROOT, text=True,
        capture_output=True, timeout=timeout, check=False,
    )


def slug(model: dict) -> str:
    value = f"{model['brand']}-{model['model']}".lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def selected_src(stdout: str, page_url: str) -> str | None:
    """Extrai o URL da imagem escolhida pelo script de selecao."""
    try:
        payload = json.loads(stdout)
        if isinstance(payload, str):
            payload = json.loads(payload)
        raw = str(payload.get("src", ""))
    except (ValueError, AttributeError):
        return None
    match = re.search(r'url\((?:"|\')?(.*?)(?:"|\')?\)', raw)
    if match:
        raw = match.group(1)
    if not raw or raw.startswith("data:"):
        return None
    return urljoin(page_url, raw)


def download_image(url: str, directory: Path) -> Path | None:
    """Descarrega o ficheiro original.

    Uma screenshot do elemento capta tudo o que estiver por cima dele - avisos
    de cookies, barras de navegacao - e nao a fotografia. Quando a imagem tem um
    URL proprio, descarrega-la e sempre preferivel.
    """
    try:
        data, _ = fetch(url)
    except Exception as error:  # noqa: BLE001 - qualquer falha cai no fallback
        print(f"  aviso: nao foi possivel descarregar {url}: {error}")
        return None
    if len(data) < 5_000:
        return None
    if data.startswith(b"\x89PNG"):
        suffix = ".png"
    elif data[:2] == b"\xff\xd8":
        suffix = ".jpg"
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        suffix = ".webp"
    else:
        return None
    target = directory / f"official{suffix}"
    target.write_bytes(data)
    for stale in directory.glob("official.*"):
        if stale != target:
            stale.unlink()
    return target


def capture(model: dict) -> Path | None:
    label = f"{model['brand']} {model['model']}"
    opened = run("open", model["official_link"])
    if opened.returncode:
        print(f"ERRO {label}: {opened.stderr.strip()}")
        return None
    run("wait", "1800")
    # Aceitar o aviso de cookies: alem de tapar a imagem, impede o lazy-load.
    run("eval", """
      (() => {
        const rx = /aceitar (todos|cookies)|accept all|concordo/i;
        const hit = [...document.querySelectorAll('button,a')].find(e => rx.test(e.innerText || ''));
        if (hit) { hit.click(); return 'clicked'; }
        return 'none';
      })()
    """)
    run("wait", "1200")
    brand_tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", model["brand"]) if len(token) > 1]
    model_tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", model["model"]) if len(token) > 1]
    script = """
      (() => {
        document.querySelectorAll('#catalog-photo').forEach(e => e.removeAttribute('id'));
        const brandTokens = __BRAND_TOKENS__;
        const modelTokens = __MODEL_TOKENS__;
        const candidates = [...document.images].filter(i => {
          const r = i.getBoundingClientRect();
          return i.naturalWidth >= 700 && i.naturalHeight >= 350 && r.width >= 300 && r.height >= 140;
        });
        let scored = candidates.map(i => {
          const text = `${i.alt} ${i.currentSrc || i.src}`.toLowerCase();
          const r = i.getBoundingClientRect();
          let score = Math.min(r.width * r.height, 1200000);
          score += modelTokens.filter(t => text.includes(t)).length * 5000000;
          score += brandTokens.filter(t => text.includes(t)).length * 1000000;
          if (/logo|icon|interior|cockpit|detail|wheel|banco|seat|customer|cliente|service|404|concept|conceito/.test(text)) score -= 8000000;
          if (/hero|exterior|front|side|model|carro|vehicle/.test(text)) score += 1500000;
          return {i, score};
        }).sort((a, b) => b.score - a.score);
        if (!scored.length) {
          scored = [...document.querySelectorAll('main *')].map(i => {
            const r = i.getBoundingClientRect();
            const bg = getComputedStyle(i).backgroundImage;
            const text = `${i.getAttribute('aria-label') || ''} ${bg}`.toLowerCase();
            let score = Math.min(r.width * r.height, 1200000);
            score += modelTokens.filter(t => text.includes(t)).length * 5000000;
            if (/interior|cockpit|detail|wheel|banco|seat|404|concept/.test(text)) score -= 8000000;
            return {i, score, valid: r.width >= 500 && r.height >= 250 && bg.includes('url(')};
          }).filter(x => x.valid).sort((a, b) => b.score - a.score);
        }
        if (!scored.length) {
          scored = [...document.querySelectorAll('canvas')].map(i => {
            const r = i.getBoundingClientRect();
            return {i, score: r.width * r.height, valid: r.width >= 500 && r.height >= 250};
          }).filter(x => x.valid).sort((a, b) => b.score - a.score);
        }
        if (!scored.length) return 'NONE';
        scored[0].i.id = 'catalog-photo';
        scored[0].i.scrollIntoView({block: 'center'});
        return JSON.stringify({src: scored[0].i.currentSrc || scored[0].i.src || getComputedStyle(scored[0].i).backgroundImage, alt: scored[0].i.alt || scored[0].i.getAttribute('aria-label') || '', score: scored[0].score});
      })()
    """.replace("__BRAND_TOKENS__", json.dumps(brand_tokens)).replace(
        "__MODEL_TOKENS__", json.dumps(model_tokens)
    )
    selected = run("eval", script)
    if selected.returncode or "NONE" in selected.stdout:
        print(f"SEM FOTO {label}")
        return None
    directory = ROOT / "web" / "assets" / "images" / "vehicles" / slug(model)
    directory.mkdir(parents=True, exist_ok=True)
    source_url = selected_src(selected.stdout, model["official_link"])
    if source_url:
        downloaded = download_image(source_url, directory)
        if downloaded:
            print(f"FOTO {label}: {source_url}")
            return downloaded

    # Fallback: canvas ou background sem URL utilizavel.
    target = directory / "official.png"
    shot = run("screenshot", "#catalog-photo", str(target))
    if shot.returncode or not target.exists() or target.stat().st_size < 5_000:
        print(f"ERRO FOTO {label}: {shot.stderr.strip()}")
        return None
    print(f"FOTO {label}: {selected.stdout.strip()}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Replace existing photos as well")
    args = parser.parse_args()
    catalog = load_catalog()
    failures: list[str] = []
    for model in catalog["models"]:
        current = ROOT / "web" / model.get("image_path", "")
        if not args.all and model.get("image_path") and current.exists() and current.stat().st_size >= 5_000:
            continue
        target = capture(model)
        if target:
            model["image_path"] = str(target.relative_to(ROOT / "web"))
        else:
            failures.append(f"{model['brand']} {model['model']}")
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if failures:
        print("Sem fotografia capturada: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

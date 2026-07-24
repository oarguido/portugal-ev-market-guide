"""Capture model-specific images from official pages with a real browser."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from compile_data import CATALOG_PATH, ROOT, load_catalog


def run(*arguments: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["agent-browser", *arguments], cwd=ROOT, text=True,
        capture_output=True, timeout=timeout, check=False,
    )


def slug(model: dict) -> str:
    value = f"{model['brand']}-{model['model']}".lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def capture(model: dict) -> Path | None:
    label = f"{model['brand']} {model['model']}"
    opened = run("open", model["official_link"])
    if opened.returncode:
        print(f"ERRO {label}: {opened.stderr.strip()}")
        return None
    run("wait", "1800")
    brand_tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", model["brand"]) if len(token) > 1]
    model_tokens = [token.lower() for token in re.findall(r"[A-Za-z0-9]+", model["model"]) if len(token) > 1]
    script = """
      (() => {
        document.querySelectorAll('#catalog-photo').forEach(e => e.removeAttribute('id'));
        const brandTokens = %s;
        const modelTokens = %s;
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
    """ % (json.dumps(brand_tokens), json.dumps(model_tokens))
    selected = run("eval", script)
    if selected.returncode or "NONE" in selected.stdout:
        print(f"SEM FOTO {label}")
        return None
    directory = ROOT / "web" / "assets" / "images" / "vehicles" / slug(model)
    directory.mkdir(parents=True, exist_ok=True)
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

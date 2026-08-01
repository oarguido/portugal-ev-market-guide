"""Capture model-specific images from official pages with a real browser."""

from __future__ import annotations

import argparse
import base64
import binascii
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


# Preferir sempre recusar: "Continuar sem aceitar" e "Rejeitar" dispensam o
# banner sem autorizar rastreio. So se nao existir alternativa e que se aceita,
# e apenas porque o banner tapa a fotografia e trava o lazy-load das imagens.
CONSENT_SCRIPT = """
  (() => {
    const recusar = /continuar sem aceitar|rejeitar tudo|rejeitar todos|rejeitar|recusar|reject all|decline|continue without accepting/i;
    const aceitar = /aceitar tudo|aceitar todos|aceitar cookies|aceitar e fechar|aceito|concordo|accept all|allow all|permitir todos|ok, entendi|entendi/i;
    const seletores = [
      '#onetrust-reject-all-handler', '.ot-pc-refuse-all-handler',
      '.didomi-continue-without-agreeing', '#didomi-notice-disagree-button',
      '#CybotCookiebotDialogBodyButtonDecline',
      '#onetrust-accept-btn-handler', '#didomi-notice-agree-button',
      '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll'
    ];
    for (const s of seletores) {
      const e = document.querySelector(s);
      if (e && e.offsetParent !== null) { e.click(); return 'seletor:' + s; }
    }
    // Muitos banners usam div/span com role=button em vez de <button>.
    const clicaveis = [...document.querySelectorAll('button,a,[role=button],input[type=button],input[type=submit]')]
      .filter(e => e.offsetParent !== null);
    for (const rx of [recusar, aceitar]) {
      const hit = clicaveis.find(e => rx.test((e.innerText || e.value || '').trim()));
      if (hit) { hit.click(); return (rx === recusar ? 'recusado:' : 'aceite:') + (hit.innerText || hit.value || '').trim().slice(0, 40); }
    }
    return 'nenhum';
  })()
"""

# Ultimo recurso: remover o proprio aviso. A Stellantis serve o banner de
# cookielaw.emea.fcagroup.com dentro de um iframe cross-origin, onde o
# JavaScript da pagina principal nao consegue clicar, e o agent-browser nao tem
# comandos de frame. Nao havendo forma de carregar no botao, tira-se o elemento
# da frente: nao consente nada, e a fotografia deixa de ficar tapada.
REMOVE_OVERLAY_SCRIPT = """
  (() => {
    let removidos = 0;
    const suspeito = /cookie|consent|privacy|privacid|gdpr|onetrust|didomi|cookielaw/i;
    document.querySelectorAll('iframe').forEach(f => {
      if (suspeito.test(f.src || '') || suspeito.test(f.id || '') || suspeito.test(f.title || '')) {
        f.remove(); removidos++;
      }
    });
    document.querySelectorAll('div,section,aside').forEach(e => {
      const pos = getComputedStyle(e).position;
      if (pos !== 'fixed' && pos !== 'sticky') return;
      const r = e.getBoundingClientRect();
      // So overlays grandes: uma barra de navegacao fixa nao tapa a fotografia.
      if (r.width * r.height < 120000) return;
      if (!suspeito.test(e.className + ' ' + e.id + ' ' + (e.innerText || '').slice(0, 300))) return;
      e.remove(); removidos++;
    });
    document.documentElement.style.overflow = 'auto';
    document.body.style.overflow = 'auto';
    return String(removidos);
  })()
"""


def dismiss_consent() -> str:
    """Dispensar o aviso de cookies antes de escolher a fotografia.

    Sem isto o banner tapa a imagem e trava o lazy-load, e o screenshot de
    recurso capturava o próprio aviso: onze das cinquenta e quatro fotografias
    do catálogo eram banners de cookies ou páginas com o diálogo por cima.

    A versão anterior procurava "aceitar todos" e as páginas portuguesas dizem
    "ACEITAR TUDO" — uma palavra de diferença que fez falhar todas as marcas
    Stellantis e a MINI, em silêncio.

    Corre duas vezes porque há banners que só aparecem depois do primeiro
    render.
    """
    resultado = run("eval", CONSENT_SCRIPT)
    if "nenhum" in resultado.stdout:
        run("wait", "900")
        resultado = run("eval", CONSENT_SCRIPT)
    if "nenhum" in resultado.stdout:
        removidos = run("eval", REMOVE_OVERLAY_SCRIPT).stdout.strip().strip('"')
        return f"removido(s) {removidos} overlay(s)"
    return resultado.stdout.strip()


def browser_download(url: str, directory: Path) -> Path | None:
    """Descarregar a imagem de dentro da própria página, em vez de com urllib.

    A Stellantis (fiat.pt, abarth.pt, jeep.pt) devolve 403 a um pedido direto ao
    CDN das imagens, mesmo com User-Agent de browser. O pedido feito de dentro da
    página passa, porque leva a origem e os cookies certos. Sem isto, todas
    aquelas marcas caíam no screenshot de recurso — que era exatamente o que
    apanhava o banner de cookies.

    Devolve os bytes por base64. É mais caro que um download normal, por isso só
    se usa quando o direto falha.
    """
    script = """
      (async () => {
        try {
          const r = await fetch(__URL__, {credentials: 'include'});
          if (!r.ok) return 'ERRO:' + r.status;
          const b = await r.blob();
          if (b.size < 5000) return 'ERRO:pequeno';
          const base64 = await new Promise(res => {
            const fr = new FileReader();
            fr.onloadend = () => res(fr.result.split(',')[1]);
            fr.readAsDataURL(b);
          });
          return b.type + '|' + base64;
        } catch (e) { return 'ERRO:' + e.message; }
      })()
    """.replace("__URL__", json.dumps(url))
    result = run("eval", script, timeout=120)
    payload = result.stdout.strip().strip('"')
    if result.returncode or payload.startswith("ERRO") or "|" not in payload:
        return None
    mime, _, data = payload.partition("|")
    try:
        raw = base64.b64decode(data)
    except (ValueError, binascii.Error):
        return None
    if len(raw) < 5_000:
        return None
    suffix = {"image/png": ".png", "image/webp": ".webp", "image/jpeg": ".jpg"}.get(mime.strip(), ".jpg")
    target = directory / f"official{suffix}"
    target.write_bytes(raw)
    return target


def capture(model: dict) -> Path | None:
    label = f"{model['brand']} {model['model']}"
    opened = run("open", model["official_link"])
    if opened.returncode:
        print(f"ERRO {label}: {opened.stderr.strip()}")
        return None
    run("wait", "1800")
    dismiss_consent()
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
          const txt = `${i.alt} ${i.currentSrc || i.src}`.toLowerCase();
          // Excluir, nao apenas penalizar: no Changan a unica foto de exterior
          // tinha 307 px de altura e era descartada pelo minimo de 350, deixando
          // so interiores de 1920x1001 — que ganhavam apesar da penalizacao.
          if (/interior|cockpit|dashboard|tablier|banco|seat|wheel|jante|detail|logo|icon/.test(txt)) return false;
          return i.naturalWidth >= 700 && i.naturalHeight >= 260 && r.width >= 300 && r.height >= 100;
        });
        let scored = candidates.map(i => {
          const text = `${i.alt} ${i.currentSrc || i.src}`.toLowerCase();
          const r = i.getBoundingClientRect();
          let score = Math.min(r.width * r.height, 1200000);
          score += modelTokens.filter(t => text.includes(t)).length * 5000000;
          score += brandTokens.filter(t => text.includes(t)).length * 1000000;
          if (/logo|icon|interior|cockpit|detail|wheel|banco|seat|customer|cliente|service|404|concept|conceito|lifestyle|people|pessoa|familia|family|portrait|retrato|passageiro|condutor|driver|banner|promo/.test(text)) score -= 8000000;
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
        # O CDN recusou o pedido direto; tentar de dentro da página.
        downloaded = browser_download(source_url, directory)
        if downloaded:
            print(f"FOTO {label} (via browser): {source_url}")
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

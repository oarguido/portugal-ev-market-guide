#!/usr/bin/env python3
"""Teste de mutação caseiro: os 102 testes apanham mesmo defeitos?

Faz uma alteração pequena e plausível ao código, corre a suíte e vê se alguém
repara. Um mutante que sobrevive é uma linha que nenhum teste protege.

Sem dependências, como o resto do projeto.
"""

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

# (ficheiro, procurar, substituir, descrição)
MUTACOES = [
    # --- regras do catálogo ---
    ("scripts/rules.py", "MAX_PRICE_EUR = 40_000", "MAX_PRICE_EUR = 45_000", "limite de preço sobe para 45.000"),
    ("scripts/rules.py", "MAX_AGE_DAYS = 45", "MAX_AGE_DAYS = 400", "frescura passa a 400 dias"),
    # --- expiração de campanhas ---
    ("scripts/expire_campaigns.py", "return dt.date.fromisoformat(expiry) < reference", "return dt.date.fromisoformat(expiry) <= reference", "expira um dia antes"),
    ("scripts/expire_campaigns.py", "if price > MAX_PRICE_EUR:", "if price >= MAX_PRICE_EUR:", "exclui o preço exatamente no limite"),
    (
        "scripts/expire_campaigns.py",
        'if not pricing.get("particular_campaign_price_vat_incl"):\n        return False',
        'if not pricing.get("particular_campaign_price_vat_incl"):\n        return True',
        "campanha ausente conta como expirada",
    ),
    # --- validação ---
    ("scripts/validate_data.py", "image.stat().st_size < 5_000", "image.stat().st_size < 1", "aceita imagens minúsculas"),
    ("scripts/validate_data.py", "elif width < MIN_IMAGE_WIDTH:", "elif width < 1:", "aceita imagens estreitas"),
    ("scripts/validate_data.py", "if len(nomes) > 1", "if len(nomes) > 99", "deixa passar fotografias repetidas"),
    ("scripts/validate_data.py", 'return (TODAY - dt.date.fromisoformat(value or "")).days > MAX_AGE_DAYS', "return False", "nada fica obsoleto"),
    # --- frescura ---
    ("scripts/validate_data.py", "if dt.date.fromisoformat(expiry) < TODAY:", "if False:", "campanhas expiradas passam despercebidas"),
    # --- cabeçalhos de imagem ---
    ("scripts/validate_data.py", 'if header[:2] == b"\\xff\\xd8":', "if False:", "JPEG deixa de ser reconhecido"),
    ("scripts/validate_data.py", 'if header[:4] == b"RIFF" and header[8:12] == b"WEBP":', "if False:", "WebP deixa de ser reconhecido"),
    # --- arquivamento ---
    ("scripts/archive_unused_images.py", "if destination.exists() and _digest(destination) == _digest(source):", "if False:", "deixa de detetar duplicados no arquivo"),
    # --- fingerprints ---
    ("scripts/update_catalog.py", 'return previous.get("sha256") != current.get("sha256")', "return False", "nunca deteta alteração de fonte"),
    # --- ligações ---
    ("scripts/validate_data.py", "VERIFIED_LINK_CODES = {200, 301, 302}", "VERIFIED_LINK_CODES = {200, 301, 302, 403, 408, 429}", "bloqueios contam como verificados"),
    # --- escape HTML ---
    ("web/assets/js/html.js", 'if (value === null || value === undefined) return "";', 'if (value === null || value === undefined) return "null";', "null passa a imprimir texto"),
    ("web/assets/js/html.js", '"&": "&amp;",', '"&": "&",', "deixa de escapar o &"),
    # --- pesquisa ---
    ("web/assets/js/search.js", "return normalizedQuery", "return true; return normalizedQuery", "pesquisa devolve tudo"),
    # --- ranking ---
    ("web/assets/js/ranking.js", "price: 0.45", "price: 0.90", "peso do preço duplica"),
]


def corre_testes() -> bool:
    """True se a suíte passa inteira."""
    py = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=RAIZ, capture_output=True, text=True, timeout=300)
    if py.returncode != 0:
        return False
    js_files = sorted(str(p) for p in (RAIZ / "tests").glob("*.test.js"))
    js = subprocess.run(["node", "--test", *js_files], cwd=RAIZ, capture_output=True, text=True, timeout=600)
    return js.returncode == 0


def main() -> int:
    print("A confirmar que a suíte passa antes de mutar...")
    if not corre_testes():
        print("A suíte já falha sem mutações. Abortado.")
        return 1
    print("Baseline verde.\n")

    sobreviventes, mortos, invalidos = [], [], []
    for ficheiro, procurar, substituir, desc in MUTACOES:
        caminho = RAIZ / ficheiro
        original = caminho.read_text(encoding="utf-8")
        if procurar not in original:
            invalidos.append(f"{ficheiro}: âncora não encontrada — {desc}")
            continue
        backup = caminho.with_suffix(caminho.suffix + ".bak")
        shutil.copy2(caminho, backup)
        try:
            caminho.write_text(original.replace(procurar, substituir, 1), encoding="utf-8")
            for pycache in RAIZ.rglob("__pycache__"):
                shutil.rmtree(pycache, ignore_errors=True)
            apanhado = not corre_testes()
        finally:
            shutil.copy2(backup, caminho)
            backup.unlink()
            for pycache in RAIZ.rglob("__pycache__"):
                shutil.rmtree(pycache, ignore_errors=True)
        (mortos if apanhado else sobreviventes).append(f"{ficheiro}: {desc}")
        print(("  MORTO       " if apanhado else "  SOBREVIVEU  ") + desc)

    total = len(mortos) + len(sobreviventes)
    print(f"\n=== {len(mortos)}/{total} mutantes apanhados ({100 * len(mortos) // total if total else 0}%) ===")
    if sobreviventes:
        print("\nSOBREVIVERAM — nenhum teste protege isto:")
        for s in sobreviventes:
            print(f"  - {s}")
    if invalidos:
        print("\nÂNCORAS INVÁLIDAS (mutação não aplicada):")
        for i in invalidos:
            print(f"  - {i}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

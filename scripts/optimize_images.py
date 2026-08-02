#!/usr/bin/env python3
"""Recomprimir as fotografias acima do orçamento, mantendo o mesmo automóvel.

Os cartões mostram a fotografia com 180 px de altura. Um ficheiro de 2,5 MB envia
ordens de grandeza mais bytes do que o ecrã usa, e a página carrega uma
fotografia por cada modelo. Reamostrar para 1600 px no lado maior e recomprimir
em JPEG tira dois terços do peso sem que se veja diferença num cartão.

O que este script NUNCA faz: trocar a fotografia por outra. A secção 10 do
AGENTS.md exige que a imagem seja do modelo exato e venha da fonte oficial —
recomprimir preserva as duas coisas, substituir não. O original vai para
`archive/` antes de ser tocado, por isso a operação é reversível.

Precisa do `sips`, que vem com o macOS. Noutro sistema, o script diz que não
consegue e não altera nada.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
ARCHIVE_ROOT = ROOT / "archive" / "originais-antes-de-recomprimir"
MAX_BYTES = 500_000
MAX_LONG_EDGE = 1600
JPEG_QUALITY = 82


def sips_available() -> bool:
    return shutil.which("sips") is not None


def recompress(source: Path, destination: Path) -> bool:
    result = subprocess.run(
        [
            "sips",
            "-Z",
            str(MAX_LONG_EDGE),
            "-s",
            "format",
            "jpeg",
            "-s",
            "formatOptions",
            str(JPEG_QUALITY),
            str(source),
            "--out",
            str(destination),
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and destination.is_file()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="escrever as fotografias recomprimidas")
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES, help="acima deste tamanho, recomprimir")
    args = parser.parse_args()

    if not sips_available():
        print("sips não está disponível; nenhuma fotografia foi alterada.")
        return 0

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    pesadas = [
        (model, ROOT / "web" / model["image_path"])
        for model in catalog["models"]
        if (ROOT / "web" / model["image_path"]).is_file() and (ROOT / "web" / model["image_path"]).stat().st_size > args.max_bytes
    ]
    if not pesadas:
        print("Nenhuma fotografia acima do orçamento.")
        return 0

    antes = depois = 0
    alterados = 0
    for model, path in pesadas:
        label = f"{model['brand']} {model['model']}"
        original = path.stat().st_size
        antes += original
        destino = path.with_suffix(".jpg")
        temporario = path.with_name(f".{path.stem}-otim.jpg")

        if not recompress(path, temporario):
            print(f"  FALHOU     {label}: sips não conseguiu converter")
            depois += original
            temporario.unlink(missing_ok=True)
            continue

        novo = temporario.stat().st_size
        if novo >= original:
            # Recomprimir e ficar maior nao ajuda ninguem.
            print(f"  MANTIDA    {label}: a recompressão não reduziu o ficheiro")
            depois += original
            temporario.unlink(missing_ok=True)
            continue

        print(f"  {'RECOMPRIME' if args.apply else 'PROPOSTA  '} {label}: {original / 1000:.0f} KB -> {novo / 1000:.0f} KB")
        depois += novo
        alterados += 1

        if not args.apply:
            temporario.unlink(missing_ok=True)
            continue

        # Guardar o original antes de lhe tocar: a operacao tem de ser reversivel.
        guardado = ARCHIVE_ROOT / path.relative_to(ROOT / "web" / "assets" / "images" / "vehicles")
        guardado.parent.mkdir(parents=True, exist_ok=True)
        if not guardado.exists():
            shutil.copy2(path, guardado)

        if destino != path:
            path.unlink()
        temporario.replace(destino)
        model["image_path"] = str(destino.relative_to(ROOT / "web"))

    print(f"\n{alterados} fotografia(s): {antes / 1e6:.1f} MB -> {depois / 1e6:.1f} MB")
    if not args.apply:
        print("Nada foi escrito. Repetir com --apply.")
        return 0

    CATALOG_PATH.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Originais guardados em {ARCHIVE_ROOT.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

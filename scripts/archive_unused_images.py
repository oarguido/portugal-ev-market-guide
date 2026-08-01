#!/usr/bin/env python3
"""List or archive vehicle images that are not referenced by the PT catalogue."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "vehicles" / "pt_market.json"
IMAGE_ROOT = ROOT / "web" / "assets" / "images" / "vehicles"
ARCHIVE_ROOT = ROOT / "archive" / "unused-vehicle-images"


def referenced_images() -> set[Path]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        (ROOT / "web" / model["image_path"]).resolve()
        for model in catalog["models"]
    }


def unused_images() -> list[Path]:
    referenced = referenced_images()
    return sorted(
        path
        for path in IMAGE_ROOT.rglob("*")
        if path.is_file()
        and path.name != ".DS_Store"
        and path.resolve() not in referenced
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def free_destination(destination: Path) -> Path:
    """Primeiro nome livre a partir de `destination`: official.png, official-2.png..."""
    if not destination.exists():
        return destination
    for index in range(2, 1_000):
        candidate = destination.with_name(f"{destination.stem}-{index}{destination.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"demasiadas colisões para {destination}")


def archive_images(images: list[Path]) -> list[str]:
    """Arquivar cada imagem, sem nunca abortar a meio nem apagar conteúdo único.

    A versão anterior levantava FileExistsError na primeira colisão. Como o
    arquivo acumula execuções anteriores, uma segunda passagem colidia quase
    sempre — e como o move acontece ficheiro a ficheiro, a operação ficava
    aplicada a meio: uns arquivados, outros não, e um traceback. Correr outra vez
    movia mais alguns e voltava a rebentar.

    Agora é idempotente:

    - destino livre: move;
    - destino ocupado com bytes iguais: a imagem já está arquivada, por isso a
      cópia ativa é removida (o conteúdo continua no arquivo, verificado por
      hash antes de remover);
    - destino ocupado com bytes diferentes: move para um nome livre, para nunca
      substituir uma imagem arquivada por outra.
    """
    notes: list[str] = []
    for source in images:
        destination = ARCHIVE_ROOT / source.relative_to(IMAGE_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        relative = source.relative_to(ROOT)
        if destination.exists() and _digest(destination) == _digest(source):
            source.unlink()
            notes.append(f"{relative}: já estava arquivada com os mesmos bytes; removida da pasta ativa")
            continue
        target = free_destination(destination)
        shutil.move(source, target)
        if target != destination:
            notes.append(f"{relative}: arquivada como {target.relative_to(ARCHIVE_ROOT)} (já existia outra com esse nome)")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="mover imagens não referenciadas para archive/unused-vehicle-images",
    )
    args = parser.parse_args()

    images = unused_images()
    total_bytes = sum(path.stat().st_size for path in images)
    for image in images:
        print(image.relative_to(ROOT))

    if not args.apply:
        print(
            f"{len(images)} imagens não referenciadas "
            f"({total_bytes / 1024 / 1024:.1f} MB); nenhuma alteração efetuada."
        )
        return 0

    notes = archive_images(images)
    if notes:
        print("\n".join(f"NOTA: {note}" for note in notes))
    print(
        f"Arquivadas {len(images)} imagens não referenciadas "
        f"({total_bytes / 1024 / 1024:.1f} MB)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

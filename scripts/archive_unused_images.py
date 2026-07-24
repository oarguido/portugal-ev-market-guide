#!/usr/bin/env python3
"""List or archive vehicle images that are not referenced by the PT catalogue."""

from __future__ import annotations

import argparse
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


def archive_images(images: list[Path]) -> None:
    for source in images:
        destination = ARCHIVE_ROOT / source.relative_to(IMAGE_ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileExistsError(f"já existe no arquivo: {destination}")
        shutil.move(source, destination)


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

    archive_images(images)
    print(
        f"Arquivadas {len(images)} imagens não referenciadas "
        f"({total_bytes / 1024 / 1024:.1f} MB)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

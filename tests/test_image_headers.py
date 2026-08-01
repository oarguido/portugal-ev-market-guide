"""Testes da leitura de cabeçalhos de imagem do validador.

O tamanho em bytes nunca disse se uma fotografia presta. Uma captura falhada da
Stellantis trouxe 4,4 KB de placeholder e passou o limite de 5 KB por pouco; três
modelos diferentes ficaram com o mesmo ficheiro byte a byte. Ler o cabeçalho
responde à pergunta certa — isto é uma imagem, e do formato que a extensão
promete?
"""

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_data import image_dimensions


def png_bytes(width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr
    chunk += struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk


def jpeg_bytes(width: int, height: int) -> bytes:
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, height, width, 3) + b"\x00" * 9
    return b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9 + sof


def webp_lossy_bytes(width: int, height: int) -> bytes:
    # Um bitstream VP8 traz 3 bytes de frame tag e o start code 9d 01 2a antes
    # das dimensões. A primeira versão deste fixture punha 10 bytes de padding e
    # falhava contra um parser que estava certo — confirmado com o `sips` em seis
    # ficheiros reais do catálogo.
    payload = b"\x00" * 3 + b"\x9d\x01\x2a" + struct.pack("<HH", width, height)
    body = b"WEBP" + b"VP8 " + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


class ImageHeaderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, name: str, payload: bytes) -> Path:
        path = self.dir / name
        path.write_bytes(payload)
        return path

    def test_le_dimensoes_de_png(self):
        self.assertEqual(image_dimensions(self.write("a.png", png_bytes(1920, 1080))), ("png", 1920, 1080))

    def test_le_dimensoes_de_jpeg(self):
        self.assertEqual(image_dimensions(self.write("a.jpg", jpeg_bytes(1280, 720))), ("jpeg", 1280, 720))

    def test_le_dimensoes_de_webp_com_perdas(self):
        self.assertEqual(image_dimensions(self.write("a.webp", webp_lossy_bytes(800, 600))), ("webp", 800, 600))

    def test_ficheiro_que_nao_e_imagem_devolve_none(self):
        self.assertIsNone(image_dimensions(self.write("a.png", b"<html>erro 403</html>" * 400)))

    def test_ficheiro_truncado_a_meio_devolve_none(self):
        """Um download interrompido tem os bytes certos ao início e mais nada."""
        self.assertIsNone(image_dimensions(self.write("a.jpg", b"\xff\xd8\xff\xe0")))

    def test_ficheiro_vazio_nao_rebenta(self):
        self.assertIsNone(image_dimensions(self.write("a.png", b"")))

    def test_ficheiro_inexistente_nao_rebenta(self):
        self.assertIsNone(image_dimensions(self.dir / "nao-existe.png"))

    def test_conteudo_png_com_extensao_jpg_e_detetado(self):
        """O caso que interessa: extensão a mentir sobre o conteúdo."""
        formato, _, _ = image_dimensions(self.write("mentira.jpg", png_bytes(900, 600)))
        self.assertEqual(formato, "png")


class RealCatalogueImageTests(unittest.TestCase):
    def test_todas_as_fotografias_do_catalogo_sao_legiveis(self):
        import json

        catalog = json.loads((ROOT / "data" / "vehicles" / "pt_market.json").read_text(encoding="utf-8"))
        for model in catalog["models"]:
            path = ROOT / "web" / model["image_path"]
            with self.subTest(modelo=f"{model['brand']} {model['model']}"):
                measured = image_dimensions(path)
                self.assertIsNotNone(measured, f"cabeçalho ilegível: {model['image_path']}")
                self.assertGreaterEqual(measured[1], 600, f"fotografia estreita demais: {model['image_path']}")


if __name__ == "__main__":
    unittest.main()

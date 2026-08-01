"""Testes do arquivamento de imagens não referenciadas.

Regressão real: `make prune-images` rebentava com FileExistsError na primeira
colisão. Como o arquivo acumula execuções anteriores e o `shutil.move` acontece
ficheiro a ficheiro, a operação ficava aplicada a meio — umas imagens arquivadas,
outras não, e um traceback. Cada nova tentativa movia mais algumas e voltava a
rebentar, sem nunca chegar ao fim.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import archive_unused_images
from archive_unused_images import archive_images, free_destination


class ArchiveImagesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.images = base / "images"
        self.archive = base / "archive"
        self.images.mkdir()
        self.archive.mkdir()
        patches = [
            mock.patch.object(archive_unused_images, "ROOT", base),
            mock.patch.object(archive_unused_images, "IMAGE_ROOT", self.images),
            mock.patch.object(archive_unused_images, "ARCHIVE_ROOT", self.archive),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def make_image(self, relative: str, content: bytes) -> Path:
        path = self.images / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def make_archived(self, relative: str, content: bytes) -> Path:
        path = self.archive / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_destino_livre_move_a_imagem(self):
        source = self.make_image("marca/official.png", b"foto")
        archive_images([source])
        self.assertFalse(source.exists())
        self.assertEqual((self.archive / "marca/official.png").read_bytes(), b"foto")

    def test_bytes_iguais_removem_a_copia_ativa_e_nao_duplicam_o_arquivo(self):
        self.make_archived("marca/official.png", b"foto")
        source = self.make_image("marca/official.png", b"foto")
        notes = archive_images([source])
        self.assertFalse(source.exists(), "a cópia ativa devia sair da pasta de imagens")
        self.assertEqual((self.archive / "marca/official.png").read_bytes(), b"foto")
        self.assertEqual(list((self.archive / "marca").iterdir()), [self.archive / "marca/official.png"])
        self.assertIn("já estava arquivada", notes[0])

    def test_bytes_diferentes_nunca_substituem_a_imagem_ja_arquivada(self):
        self.make_archived("marca/official.png", b"antiga")
        source = self.make_image("marca/official.png", b"nova")
        notes = archive_images([source])
        self.assertEqual((self.archive / "marca/official.png").read_bytes(), b"antiga")
        self.assertEqual((self.archive / "marca/official-2.png").read_bytes(), b"nova")
        self.assertIn("official-2.png", notes[0])

    def test_uma_colisao_nao_impede_o_arquivamento_das_restantes(self):
        """O defeito exato: abortar a meio deixava a operação por concluir."""
        self.make_archived("b/official.png", b"antiga")
        sources = [
            self.make_image("a/official.png", b"a"),
            self.make_image("b/official.png", b"diferente"),
            self.make_image("c/official.png", b"c"),
        ]
        archive_images(sources)
        for source in sources:
            self.assertFalse(source.exists(), f"{source} ficou por arquivar")
        self.assertEqual((self.archive / "a/official.png").read_bytes(), b"a")
        self.assertEqual((self.archive / "c/official.png").read_bytes(), b"c")

    def test_correr_duas_vezes_seguidas_e_seguro(self):
        source = self.make_image("marca/official.png", b"foto")
        archive_images([source])
        again = self.make_image("marca/official.png", b"foto")
        archive_images([again])  # não pode levantar
        self.assertFalse(again.exists())

    def test_free_destination_escolhe_o_primeiro_nome_livre(self):
        self.make_archived("marca/official.png", b"1")
        self.make_archived("marca/official-2.png", b"2")
        chosen = free_destination(self.archive / "marca/official.png")
        self.assertEqual(chosen.name, "official-3.png")

    def test_free_destination_devolve_o_proprio_caminho_quando_esta_livre(self):
        target = self.archive / "marca/official.png"
        self.assertEqual(free_destination(target), target)


if __name__ == "__main__":
    unittest.main()

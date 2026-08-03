"""Testes das peças do pipeline que um teste de mutação mostrou desprotegidas.

Nenhuma delas era coberta: podiam ser desligadas e a suíte ficava verde. São
peças pequenas, mas cada uma existe por causa de um defeito real — o `evaluate`
descasca aspas porque cada chamador se esquecia de o fazer, o radar dedupe porque
propunha modelos que já estavam no catálogo, o `optimize_images` recusa
recompressões maiores porque não faz sentido piorar o ficheiro, e o carimbo do
bundle existe porque o browser servia o catálogo antigo.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import browser
import compile_data
import discover_models
import optimize_images


def resultado(stdout: str, returncode: int = 0):
    return subprocess.CompletedProcess(args=["agent-browser"], returncode=returncode, stdout=stdout, stderr="")


class CamadaDoBrowser(unittest.TestCase):
    def test_evaluate_descasca_as_aspas_do_json(self):
        """O agent-browser devolve JSON, por isso uma string vem entre aspas."""
        with mock.patch.object(browser, "run", return_value=resultado('"olá mundo"')):
            self.assertEqual(browser.evaluate("x"), "olá mundo")

    def test_evaluate_deixa_intacto_o_que_nao_e_json(self):
        with mock.patch.object(browser, "run", return_value=resultado("texto simples")):
            self.assertEqual(browser.evaluate("x"), "texto simples")

    def test_evaluate_mantem_json_estruturado_como_texto(self):
        """Um objeto continua a poder ser desserializado pelo chamador."""
        with mock.patch.object(browser, "run", return_value=resultado('{"a": 1}')):
            self.assertEqual(json.loads(browser.evaluate("x")), {"a": 1})

    def test_evaluate_devolve_vazio_quando_o_comando_falha(self):
        with mock.patch.object(browser, "run", return_value=resultado("ignorado", returncode=1)):
            self.assertEqual(browser.evaluate("x"), "")

    def test_page_text_devolve_none_quando_a_pagina_vem_vazia(self):
        """None e "" significam coisas diferentes: sem conteúdo vs conteúdo vazio."""
        with mock.patch.object(browser, "open_page", return_value=True), mock.patch.object(browser, "run", return_value=resultado("   ")):
            self.assertIsNone(browser.page_text("https://exemplo.pt"))

    def test_page_text_devolve_none_quando_a_pagina_nao_abre(self):
        with mock.patch.object(browser, "open_page", return_value=False):
            self.assertIsNone(browser.page_text("https://exemplo.pt"))

    def test_page_text_devolve_o_texto_quando_existe(self):
        with mock.patch.object(browser, "open_page", return_value=True), mock.patch.object(browser, "run", return_value=resultado("Modelo Elétrico 29.990 €")):
            self.assertEqual(browser.page_text("https://exemplo.pt"), "Modelo Elétrico 29.990 €")


class RadarDeMercado(unittest.TestCase):
    def catalogo(self, *nomes) -> dict:
        return {"models": [{"brand": n.split()[0], "model": " ".join(n.split()[1:])} for n in nomes]}

    def test_modelo_ja_no_catalogo_nao_e_proposto(self):
        c = self.catalogo("Kia EV3")
        self.assertEqual(discover_models.unknown_from_names(["kia ev3"], c), [])

    def test_variante_do_mesmo_modelo_nao_e_proposta(self):
        """ "Kia EV3 GT Line" não é um modelo novo em relação a "Kia EV3"."""
        c = self.catalogo("Kia EV3")
        self.assertEqual(discover_models.unknown_from_names(["kia ev3 gt line"], c), [])

    def test_modelo_novo_e_proposto(self):
        c = self.catalogo("Kia EV3")
        self.assertEqual(discover_models.unknown_from_names(["kia ev9"], c), ["kia ev9"])

    def test_acentos_e_pontuacao_nao_criam_falsos_candidatos(self):
        c = self.catalogo("Citroën ë-C3")
        self.assertEqual(discover_models.unknown_from_names(["citroen e c3"], c), [])

    def test_candidatos_repetidos_aparecem_uma_vez(self):
        c = self.catalogo("Kia EV3")
        self.assertEqual(discover_models.unknown_from_names(["kia ev9", "kia ev9"], c), ["kia ev9"])

    def test_grafia_colada_do_mesmo_modelo_nao_e_proposta(self):
        """A electrifying.com escreve "e208"; o catálogo escreve "E-208".

        Medido contra a fonte real em 2026-08-03: era o único falso candidato em
        285. Comparar só por prefixo da forma com espaços não o apanha, porque a
        diferença está a meio da string, não no fim.
        """
        c = self.catalogo("Peugeot E-208")
        self.assertEqual(discover_models.unknown_from_names(["peugeot e208"], c), [])

    def test_modelo_diferente_com_grafia_colada_continua_a_ser_proposto(self):
        """Compactar não pode cegar o radar: o e-2008 não é o e-208."""
        c = self.catalogo("Peugeot E-208")
        self.assertEqual(discover_models.unknown_from_names(["peugeot e2008"], c), ["peugeot e2008"])

    def test_celula_sem_nome_legivel_nao_vira_candidato(self):
        """Um travessão de tabela não é um carro: não há o que confirmar em fonte oficial."""
        c = self.catalogo("Kia EV3")
        rows = [["Modelo", "Preço"], ["—", "—"], ["", ""], ["   ", "n.d."]]
        self.assertEqual(discover_models.unknown_from_rows(rows, c), [])

    def test_grafia_colada_tambem_e_filtrada_na_tabela(self):
        """O mesmo modelo lido de uma tabela HTML, não de um link, tem de dar o mesmo."""
        c = self.catalogo("Peugeot E-208")
        rows = [["Modelo", "Preço"], ["Peugeot e208", "31.900 €"]]
        self.assertEqual(discover_models.unknown_from_rows(rows, c), [])


class OtimizacaoDeImagens(unittest.TestCase):
    def cenario(self, tmp: Path, tamanho_recomprimido: int) -> tuple[dict, list[str]]:
        """Corre o otimizador com uma recompressão de tamanho controlado."""
        raiz = Path(tmp)
        # O arquivo deriva o caminho de web/assets/images/vehicles: a fixture tem
        # de respeitar a mesma estrutura.
        pasta = raiz / "web" / "assets" / "images" / "vehicles" / "marca-x"
        pasta.mkdir(parents=True)
        original = b"\x89PNG\r\n\x1a\n" + b"\x00" * 600_000
        (pasta / "grande.png").write_bytes(original)
        rel = "assets/images/vehicles/marca-x/grande.png"
        catalogo = {"models": [{"brand": "M", "model": "X", "image_path": rel}]}
        (raiz / "cat.json").write_text(json.dumps(catalogo), encoding="utf-8")

        def falsa_recompressao(_src, dst):
            dst.write_bytes(b"\xff\xd8" + b"\x00" * tamanho_recomprimido)
            return True

        with (
            mock.patch.object(optimize_images, "recompress", side_effect=falsa_recompressao),
            mock.patch.object(optimize_images, "sips_available", return_value=True),
            mock.patch.object(optimize_images, "CATALOG_PATH", raiz / "cat.json"),
            mock.patch.object(optimize_images, "ARCHIVE_ROOT", raiz / "arquivo"),
            mock.patch.object(optimize_images, "ROOT", raiz),
            mock.patch.object(sys, "argv", ["optimize_images.py", "--apply"]),
        ):
            optimize_images.main()
        return json.loads((raiz / "cat.json").read_text(encoding="utf-8")), list(pasta.iterdir())

    def test_recompressao_maior_e_descartada(self):
        """Recomprimir e ficar maior não ajuda ninguém: o original fica."""
        with tempfile.TemporaryDirectory() as tmp:
            catalogo, ficheiros = self.cenario(tmp, 900_000)
            # O caminho no catálogo não muda e o PNG original continua lá.
            self.assertEqual(catalogo["models"][0]["image_path"], "assets/images/vehicles/marca-x/grande.png")
            self.assertEqual([f.name for f in ficheiros], ["grande.png"])
            self.assertGreater(ficheiros[0].stat().st_size, 500_000)

    def test_recompressao_menor_e_aplicada(self):
        with tempfile.TemporaryDirectory() as tmp:
            catalogo, ficheiros = self.cenario(tmp, 100_000)
            self.assertEqual(catalogo["models"][0]["image_path"], "assets/images/vehicles/marca-x/grande.jpg")
            self.assertIn("grande.jpg", [f.name for f in ficheiros])
            self.assertNotIn("grande.png", [f.name for f in ficheiros])

    def test_o_original_e_guardado_antes_de_ser_substituido(self):
        """A operação tem de ser reversível."""
        with tempfile.TemporaryDirectory() as tmp:
            self.cenario(tmp, 100_000)
            guardado = Path(tmp) / "arquivo" / "marca-x" / "grande.png"
            self.assertTrue(guardado.is_file(), "o original devia estar no arquivo")
            self.assertGreater(guardado.stat().st_size, 500_000)


class CarimboDoBundle(unittest.TestCase):
    def test_o_carimbo_muda_quando_o_bundle_muda(self):
        """Sem isto o browser continua a servir o catálogo antigo."""
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "index.html"
            index.write_text('<script src="assets/js/car_data.js"></script>', encoding="utf-8")
            with mock.patch.object(compile_data, "INDEX_PATH", index):
                self.assertTrue(compile_data.stamp_index("conteudo A"))
                primeiro = index.read_text(encoding="utf-8")
                self.assertRegex(primeiro, r'car_data\.js\?v=[0-9a-f]{12}"')

                self.assertTrue(compile_data.stamp_index("conteudo B"))
                self.assertNotEqual(index.read_text(encoding="utf-8"), primeiro)

    def test_bundle_igual_nao_mexe_no_index(self):
        """Reescrever com o mesmo conteúdo só churnava o mtime."""
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "index.html"
            index.write_text('<script src="assets/js/car_data.js"></script>', encoding="utf-8")
            with mock.patch.object(compile_data, "INDEX_PATH", index):
                compile_data.stamp_index("mesmo")
                depois = index.read_text(encoding="utf-8")
                self.assertFalse(compile_data.stamp_index("mesmo"))
                self.assertEqual(index.read_text(encoding="utf-8"), depois)


if __name__ == "__main__":
    unittest.main()

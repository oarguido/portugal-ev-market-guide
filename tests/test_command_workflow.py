"""Regressões dos comandos offline e do relatório de trabalho pendente."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from report_pending import build_sections


class RelatorioPendenteTests(unittest.TestCase):
    def test_preco_sem_pvp_e_condicoes_de_equivalencia_geram_acao_e_fonte(self):
        catalog = {
            "models": [
                {
                    "brand": "Marca",
                    "model": "Modelo",
                    "official_link": "https://marca.pt/modelo",
                    "data_sources": [{"url": "https://marca.pt/precos"}],
                    "variants": [
                        {
                            "name": "Base",
                            "pricing": {
                                "offers": [
                                    {
                                        "classification": "reference",
                                        "proof": {"status": "legacy_unverified"},
                                        "conditions": "Equivalente com IVA; confirmar despesas.",
                                    }
                                ]
                            },
                        }
                    ],
                }
            ]
        }

        sections = dict(build_sections(catalog, {"dealers": []}, {}))
        pending = sections["PREÇOS E CONDIÇÕES — confirmar elegíveis; referências publicáveis com rótulo explícito"]
        self.assertGreaterEqual(len(pending), 1)
        report = " ".join(pending)
        self.assertIn("referência legada", report)
        self.assertIn("https://marca.pt/precos", report)
        self.assertIn("publicável com rótulo explícito", report)
        self.assertNotIn("resolver antes de publicar", report)


class MakefileWorkflowTests(unittest.TestCase):
    def test_alvos_documentados_existem(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        for target in ("update", "update-accept", "update-photos", "update-photos-all", "prune-images", "freshness", "sequential"):
            with self.subTest(target=target):
                self.assertRegex(makefile, rf"(?m)^{target}:")

    def test_update_em_modo_dry_run_nao_aplica_propostas_de_precos(self):
        result = subprocess.run(["make", "-n", "update"], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scripts/refresh_prices.py", result.stdout)
        self.assertNotIn("scripts/refresh_prices.py --apply", result.stdout)
        self.assertNotIn("-@python3 -u scripts/refresh_prices.py", result.stdout)


if __name__ == "__main__":
    unittest.main()

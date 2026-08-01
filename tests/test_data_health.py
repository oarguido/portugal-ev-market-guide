"""Testes dos sinais que só aparecem com a passagem do tempo ou com o peso dos
ficheiros.

Estes são os sinais em que o workflow agendado `data-health.yml` se apoia. Sem
testes, o workflow podia ficar verde para sempre por a deteção estar quebrada, e
ninguém notaria — é precisamente o modo de falha que ele existe para evitar.
"""

import datetime as dt
import itertools
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_data
from validate_data import image_budget_warnings, interleave_by_host, staleness_warnings

EMPTY_DEALERS: dict = {"dealers": []}


def catalog_verified_on(date: str) -> dict:
    return {
        "discovery_sources": [],
        "models": [
            {
                "brand": "Marca",
                "model": "Modelo",
                "last_verified": date,
                "image_path": "assets/images/nao-existe.jpg",
                "variants": [{"name": "Base", "pricing": {}}],
            }
        ],
    }


class StalenessTests(unittest.TestCase):
    def test_verificacao_recente_nao_gera_aviso(self):
        recent = (validate_data.TODAY - dt.timedelta(days=validate_data.MAX_AGE_DAYS - 1)).isoformat()
        self.assertEqual(staleness_warnings(catalog_verified_on(recent), EMPTY_DEALERS), [])

    def test_verificacao_no_limite_exato_ainda_nao_gera_aviso(self):
        limit = (validate_data.TODAY - dt.timedelta(days=validate_data.MAX_AGE_DAYS)).isoformat()
        self.assertEqual(staleness_warnings(catalog_verified_on(limit), EMPTY_DEALERS), [])

    def test_verificacao_um_dia_acima_do_limite_gera_aviso(self):
        stale = (validate_data.TODAY - dt.timedelta(days=validate_data.MAX_AGE_DAYS + 1)).isoformat()
        notes = staleness_warnings(catalog_verified_on(stale), EMPTY_DEALERS)
        self.assertEqual(len(notes), 1)
        self.assertIn("Marca Modelo", notes[0])
        self.assertIn(str(validate_data.MAX_AGE_DAYS), notes[0])

    def test_campanha_expirada_gera_aviso_e_campanha_valida_nao(self):
        def catalog_with_expiry(expiry: str) -> dict:
            data = catalog_verified_on(validate_data.TODAY.isoformat())
            data["models"][0]["variants"][0]["pricing"] = {
                "particular_campaign_price_vat_incl": 29_990,
                "campaign_valid_until": expiry,
            }
            return data

        expired = (validate_data.TODAY - dt.timedelta(days=1)).isoformat()
        future = (validate_data.TODAY + dt.timedelta(days=1)).isoformat()
        self.assertIn("campanha expirada", " ".join(staleness_warnings(catalog_with_expiry(expired), EMPTY_DEALERS)))
        self.assertEqual(staleness_warnings(catalog_with_expiry(future), EMPTY_DEALERS), [])

    def test_campanha_sem_preco_de_campanha_nao_expira(self):
        """Uma validade órfã sem campanha ativa não é uma campanha expirada."""
        data = catalog_verified_on(validate_data.TODAY.isoformat())
        data["models"][0]["variants"][0]["pricing"] = {
            "particular_campaign_price_vat_incl": None,
            "campaign_valid_until": (validate_data.TODAY - dt.timedelta(days=30)).isoformat(),
        }
        self.assertEqual(staleness_warnings(data, EMPTY_DEALERS), [])

    def test_concessionario_antigo_gera_aviso(self):
        stale = (validate_data.TODAY - dt.timedelta(days=validate_data.MAX_AGE_DAYS + 1)).isoformat()
        dealers = {"dealers": [{"brand": "Marca", "verified_on": stale}]}
        notes = staleness_warnings(catalog_verified_on(validate_data.TODAY.isoformat()), dealers)
        self.assertEqual(len(notes), 1)
        self.assertIn("Concessionário Marca", notes[0])

    def test_o_catalogo_real_fica_obsoleto_quando_o_tempo_avanca(self):
        """A deteção tem de disparar sobre os dados reais, não só sobre fixtures.

        Prova o comportamento que o workflow agendado deve apanhar: à data da
        verificação mais recente nada está obsoleto, e MAX_AGE_DAYS + 1 dias
        depois está tudo.

        As duas datas são fixadas com mock e derivadas do próprio catálogo. Sem
        isso o teste passaria a falhar por efeito do calendário e não por
        regressão — exatamente o que a separação entre `make validate` e
        `make freshness` existe para evitar.
        """
        catalog = validate_data.load_catalog()
        dealers = validate_data.load_dealers()
        newest = dt.date.fromisoformat(max(model["last_verified"] for model in catalog["models"]))

        def outdated_on(day: dt.date) -> list[str]:
            with mock.patch.object(validate_data, "TODAY", day):
                # Só os avisos de verificação obsoleta: uma campanha expirada é um
                # sinal diferente, e depende de datas que o catálogo traz de fora.
                return [note for note in staleness_warnings(catalog, dealers) if "verificação tem mais de" in note]

        self.assertEqual(outdated_on(newest), [], "nada devia estar obsoleto na data da verificação mais recente")

        future = newest + dt.timedelta(days=validate_data.MAX_AGE_DAYS + 1)
        outdated = outdated_on(future)

        self.assertEqual(
            len(outdated),
            len(catalog["models"]) + len(dealers["dealers"]) + len(catalog["discovery_sources"]),
            "todas as verificações deviam estar obsoletas nessa data",
        )
        for model in catalog["models"]:
            label = f"{model['brand']} {model['model']}"
            self.assertTrue(
                any(note.startswith(f"{label}:") for note in outdated),
                f"{label} não foi reportado como obsoleto",
            )


class ImageBudgetTests(unittest.TestCase):
    def test_fotografia_dentro_do_orcamento_nao_gera_aviso(self):
        with mock.patch.object(validate_data, "MAX_IMAGE_BYTES", 10**9), mock.patch.object(validate_data, "MAX_IMAGE_TOTAL_BYTES", 10**12):
            self.assertEqual(image_budget_warnings(validate_data.load_catalog()), [])

    def test_resumo_de_uma_linha_por_omissao_e_lista_completa_com_detalhe(self):
        catalog = validate_data.load_catalog()
        summary = image_budget_warnings(catalog)
        detailed = image_budget_warnings(catalog, detailed=True)
        # O resumo não pode crescer com o número de fotografias pesadas: é o que
        # impede o `make validate` de afogar os avisos de frescura.
        self.assertLessEqual(len(summary), 2)
        self.assertGreater(len(detailed), len(summary))
        self.assertTrue(any("excedem" in note for note in summary))

    def test_a_lista_detalhada_vem_da_mais_pesada_para_a_mais_leve(self):
        detailed = image_budget_warnings(validate_data.load_catalog(), detailed=True)
        sizes = [int(note.split("fotografia com ")[1].split(" KB")[0]) for note in detailed if "fotografia com" in note]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_fotografia_ausente_nao_conta_para_o_orcamento(self):
        """Uma imagem em falta é erro de validate_catalog, não de orçamento."""
        self.assertEqual(image_budget_warnings(catalog_verified_on(validate_data.TODAY.isoformat())), [])


class LinkScheduleTests(unittest.TestCase):
    def test_nenhuma_url_se_perde_nem_se_duplica(self):
        urls = [f"https://host{index % 7}.pt/pagina{index}" for index in range(40)]
        self.assertEqual(sorted(interleave_by_host(urls)), sorted(urls))

    def test_pedidos_consecutivos_nao_atingem_o_mesmo_dominio(self):
        urls = [f"https://a.pt/{index}" for index in range(3)] + [f"https://b.pt/{index}" for index in range(3)]
        hosts = [url.split("/")[2] for url in interleave_by_host(urls)]
        for first, second in itertools.pairwise(hosts):
            self.assertNotEqual(first, second, f"dois pedidos seguidos para {first}")

    def test_um_unico_dominio_mantem_a_ordem(self):
        urls = ["https://a.pt/1", "https://a.pt/2", "https://a.pt/3"]
        self.assertEqual(interleave_by_host(urls), urls)

    def test_lista_vazia_nao_rebenta(self):
        self.assertEqual(interleave_by_host([]), [])


if __name__ == "__main__":
    unittest.main()

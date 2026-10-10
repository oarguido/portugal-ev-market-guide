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

import rules
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
                "offers": [{
                    "kind": "campaign_price",
                    "amount_eur": 29_990,
                    "validity": {"valid_from": None, "valid_until": expiry},
                }],
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
            "offers": [{
                "kind": "list_price",
                "amount_eur": 29_990,
                "validity": {"valid_from": None, "valid_until": (validate_data.TODAY - dt.timedelta(days=30)).isoformat()},
            }],
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

        Prova o comportamento que o workflow agendado deve apanhar, por tipo de
        verificação (modelos, concessionários, fontes de descoberta), porque cada
        tipo é reverificado em datas diferentes: MAX_AGE_DAYS exatos depois da
        verificação mais antiga desse tipo nenhum item está obsoleto, e
        MAX_AGE_DAYS + 1 dias depois da mais recente estão todos.

        As datas são fixadas com mock e derivadas do próprio catálogo. Sem isso o
        teste passaria a falhar por efeito do calendário e não por regressão —
        exatamente o que a separação entre `make validate` e `make freshness`
        existe para evitar.
        """
        catalog = validate_data.load_catalog()
        dealers = validate_data.load_dealers()
        groups = {
            "modelos": (
                [model["last_verified"] for model in catalog["models"]],
                lambda note: not note.startswith(("Concessionário ", "Fonte de descoberta ")),
                len(catalog["models"]),
            ),
            "concessionários": (
                [dealer["verified_on"] for dealer in dealers["dealers"]],
                lambda note: note.startswith("Concessionário "),
                len(dealers["dealers"]),
            ),
            "fontes de descoberta": (
                [source["verified_on"] for source in catalog["discovery_sources"]],
                lambda note: note.startswith("Fonte de descoberta "),
                len(catalog["discovery_sources"]),
            ),
        }

        def outdated_on(day: dt.date, belongs) -> list[str]:
            with mock.patch.object(validate_data, "TODAY", day):
                # Só os avisos de verificação obsoleta: uma campanha expirada é um
                # sinal diferente, e depende de datas que o catálogo traz de fora.
                notes = staleness_warnings(catalog, dealers)
            return [note for note in notes if "verificação tem mais de" in note and belongs(note)]

        for name, (dates, belongs, total) in groups.items():
            if not dates:
                continue
            with self.subTest(tipo=name):
                newest = dt.date.fromisoformat(max(dates))
                oldest = dt.date.fromisoformat(min(dates))
                limit = oldest + dt.timedelta(days=validate_data.MAX_AGE_DAYS)
                self.assertEqual(
                    outdated_on(limit, belongs), [], f"nenhum item de {name} devia estar obsoleto ao fim de MAX_AGE_DAYS exatos"
                )
                future = newest + dt.timedelta(days=validate_data.MAX_AGE_DAYS + 1)
                self.assertEqual(len(outdated_on(future, belongs)), total, f"todos os itens de {name} deviam estar obsoletos")
        for model in catalog["models"]:
            label = f"{model['brand']} {model['model']}"
            future = dt.date.fromisoformat(model["last_verified"]) + dt.timedelta(days=validate_data.MAX_AGE_DAYS + 1)
            self.assertTrue(
                any(note.startswith(f"{label}:") for note in outdated_on(future, groups["modelos"][1])),
                f"{label} não foi reportado como obsoleto",
            )


class ExpiredCampaignTests(unittest.TestCase):
    """Uma campanha expirada só é um achado enquanto a elegibilidade gravada ainda conta com ela.

    `expire_campaigns.py` mantém a oferta expirada como histórico (de propósito) e
    recalcula a elegibilidade. Depois disso a campanha expirada já não é trabalho
    por fazer; reportá-la para sempre tornava `make freshness` impossível de passar.
    """

    def _variant_with_expired_campaign(self):
        catalog = validate_data.load_catalog()
        for model in catalog["models"]:
            for variant in model["variants"]:
                for offer in variant.get("pricing", {}).get("offers", []):
                    expiry = (offer.get("validity") or {}).get("valid_until")
                    if offer.get("kind") != "campaign_price" or not expiry:
                        continue
                    day_after = dt.date.fromisoformat(expiry) + dt.timedelta(days=1)
                    before = rules.variant_eligibility_tier(variant, dt.date.fromisoformat(expiry))
                    after = rules.variant_eligibility_tier(variant, day_after)
                    if before == "confirmed_eligible" and after != before:
                        return model, variant, day_after, after
        self.skipTest("o catálogo não tem nenhuma campanha cuja expiração mude a elegibilidade")

    def _expired_notes(self, model, variant, day):
        catalog = {"discovery_sources": [], "models": [{**model, "last_verified": day.isoformat(), "variants": [variant]}]}
        with mock.patch.object(validate_data, "TODAY", day):
            return [note for note in staleness_warnings(catalog, EMPTY_DEALERS) if "campanha expirada" in note]

    def test_campanha_expirada_ja_recalculada_nao_e_reportada(self):
        model, variant, day, recomputed = self._variant_with_expired_campaign()
        variant = {**variant, "eligibility_tier": recomputed, "eligibility_status": recomputed}
        self.assertEqual(self._expired_notes(model, variant, day), [])

    def test_campanha_expirada_por_recalcular_continua_a_ser_reportada(self):
        model, variant, day, _ = self._variant_with_expired_campaign()
        variant = {**variant, "eligibility_tier": "confirmed_eligible", "eligibility_status": "confirmed_eligible"}
        self.assertEqual(len(self._expired_notes(model, variant, day)), 1)


class ImageBudgetTests(unittest.TestCase):
    def test_fotografia_dentro_do_orcamento_nao_gera_aviso(self):
        with mock.patch.object(validate_data, "MAX_IMAGE_BYTES", 10**9), mock.patch.object(validate_data, "MAX_IMAGE_TOTAL_BYTES", 10**12):
            self.assertEqual(image_budget_warnings(validate_data.load_catalog()), [])

    def test_resumo_de_uma_linha_por_omissao_e_lista_completa_com_detalhe(self):
        # Limite artificialmente baixo para que o catálogo real tenha sempre
        # fotografias acima dele. Antes isto dependia de existirem fotografias
        # pesadas de verdade, e passou a falhar no dia em que foram todas
        # recomprimidas — uma regressão inventada, como a do calendário.
        catalog = validate_data.load_catalog()
        with mock.patch.object(validate_data, "MAX_IMAGE_BYTES", 50_000):
            summary = image_budget_warnings(catalog)
            detailed = image_budget_warnings(catalog, detailed=True)
        # O resumo não pode crescer com o número de fotografias pesadas: é o que
        # impede o `make validate` de afogar os avisos de frescura.
        self.assertLessEqual(len(summary), 2)
        self.assertGreater(len(detailed), len(summary))
        self.assertTrue(any("excedem" in note for note in summary))

    def test_a_lista_detalhada_vem_da_mais_pesada_para_a_mais_leve(self):
        with mock.patch.object(validate_data, "MAX_IMAGE_BYTES", 50_000):
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

"""Testes da remoção de campanhas expiradas e da cascata de elegibilidade.

Este passo apaga dados do catálogo, por isso os limites importam mais do que o
caminho feliz: uma campanha sem validade publicada não pode ser declarada
expirada, e uma variante só sai quando o preço que resta é mesmo inelegível.
"""

import datetime as dt
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from expire_campaigns import expire_catalog, is_expired

HOJE = dt.date(2026, 8, 1)


def pricing(campaign=None, expiry=None, listed=None):
    return {
        "particular_campaign_price_vat_incl": campaign,
        "particular_list_price_vat_incl": listed,
        "campaign_conditions": "condições" if campaign else None,
        "campaign_valid_until": expiry,
    }


def catalog(*variants, brand="Marca", model="Modelo"):
    return {"models": [{"brand": brand, "model": model, "variants": [{"name": f"v{i}", "pricing": p} for i, p in enumerate(variants)]}]}


class IsExpiredTests(unittest.TestCase):
    def test_validade_passada_com_campanha_expira(self):
        self.assertTrue(is_expired(pricing(30_000, "2026-07-31"), HOJE))

    def test_validade_de_hoje_ainda_nao_expira(self):
        """A campanha vale até ao fim do dia indicado."""
        self.assertFalse(is_expired(pricing(30_000, "2026-08-01"), HOJE))

    def test_validade_futura_nao_expira(self):
        self.assertFalse(is_expired(pricing(30_000, "2026-08-31"), HOJE))

    def test_campanha_sem_validade_publicada_nunca_expira_sozinha(self):
        """AGENTS.md secção 8: sem validade publicada guarda-se null.

        Declarar expirada uma campanha sem data seria inventar um facto. Tem de
        ser confirmada na fonte, não apagada por omissão.
        """
        self.assertFalse(is_expired(pricing(30_000, None), HOJE))

    def test_validade_orfa_sem_campanha_nao_conta(self):
        self.assertFalse(is_expired(pricing(None, "2020-01-01"), HOJE))

    def test_data_invalida_nao_rebenta_nem_expira(self):
        self.assertFalse(is_expired(pricing(30_000, "não é data"), HOJE))


class CascadeTests(unittest.TestCase):
    def test_campanha_expirada_com_pvp_elegivel_mantem_a_variante(self):
        data = catalog(pricing(37_830, "2026-07-31", listed=39_000))
        report = expire_catalog(data, {"dealers": []}, HOJE)
        variant = data["models"][0]["variants"][0]
        self.assertIsNone(variant["pricing"]["particular_campaign_price_vat_incl"])
        self.assertIsNone(variant["pricing"]["campaign_conditions"])
        self.assertIsNone(variant["pricing"]["campaign_valid_until"])
        self.assertEqual(variant["pricing"]["particular_list_price_vat_incl"], 39_000)
        self.assertTrue(any("CAMPANHA EXPIRADA" in line for line in report))
        self.assertFalse(any("VARIANTE REMOVIDA" in line for line in report))

    def test_campanha_expirada_com_pvp_acima_do_limite_remove_a_variante(self):
        data = catalog(pricing(35_003, "2026-07-31", listed=47_003))
        expire_catalog(data, {"dealers": []}, HOJE)
        self.assertEqual(data["models"], [], "o modelo devia sair por ficar sem variantes elegíveis")

    def test_campanha_expirada_sem_pvp_remove_a_variante(self):
        data = catalog(pricing(30_000, "2026-07-31", listed=None))
        report = expire_catalog(data, {"dealers": []}, HOJE)
        self.assertEqual(data["models"], [])
        self.assertTrue(any("ficou sem preço elegível" in line for line in report))

    def test_variante_elegivel_sobrevive_e_o_modelo_fica(self):
        data = catalog(
            pricing(35_003, "2026-07-31", listed=47_003),
            pricing(None, None, listed=29_000),
        )
        expire_catalog(data, {"dealers": []}, HOJE)
        self.assertEqual(len(data["models"]), 1)
        self.assertEqual([v["name"] for v in data["models"][0]["variants"]], ["v1"])

    def test_campanha_valida_fica_intacta(self):
        data = catalog(pricing(26_560, "2026-08-31", listed=28_190))
        report = expire_catalog(data, {"dealers": []}, HOJE)
        self.assertEqual(report, [])
        self.assertEqual(data["models"][0]["variants"][0]["pricing"]["particular_campaign_price_vat_incl"], 26_560)

    def test_marca_sem_modelos_perde_o_concessionario(self):
        data = catalog(pricing(35_003, "2026-07-31", listed=47_003), brand="Jeep")
        dealers = {"dealers": [{"brand": "Jeep"}, {"brand": "Kia"}]}
        report = expire_catalog(data, dealers, HOJE)
        self.assertEqual([d["brand"] for d in dealers["dealers"]], [])
        self.assertTrue(any("STAND REMOVIDO" in line and "Jeep" in line for line in report))

    def test_marca_que_sobrevive_mantem_o_concessionario(self):
        data = catalog(pricing(None, None, listed=29_000), brand="Kia")
        dealers = {"dealers": [{"brand": "Kia"}]}
        expire_catalog(data, dealers, HOJE)
        self.assertEqual([d["brand"] for d in dealers["dealers"]], ["Kia"])

    def test_pvp_exatamente_no_limite_continua_elegivel(self):
        data = catalog(pricing(35_000, "2026-07-31", listed=40_000))
        expire_catalog(data, {"dealers": []}, HOJE)
        self.assertEqual(len(data["models"]), 1)

    def test_correr_duas_vezes_nao_muda_mais_nada(self):
        data = catalog(pricing(37_830, "2026-07-31", listed=39_000))
        expire_catalog(data, {"dealers": []}, HOJE)
        self.assertEqual(expire_catalog(data, {"dealers": []}, HOJE), [])


if __name__ == "__main__":
    unittest.main()

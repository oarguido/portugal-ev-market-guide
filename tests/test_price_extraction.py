"""Testes da barreira que impede um preço inventado de entrar no catálogo.

O `refresh_prices.py` põe um modelo de linguagem a ler páginas oficiais. Isso só
é aceitável por causa de uma coisa: nada entra sem a citação literal da página, e
o número extraído tem de aparecer mesmo no texto. Um teste de mutação mostrou que
essa barreira não tinha um único teste — podia ser desligada em silêncio, e o
catálogo passaria a aceitar o que o modelo imaginasse.

É a verificação mais consequente do projeto inteiro.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from refresh_prices import apply_proposals, date_appears, digits, target_variant, verify

PAGINA = (
    "Novo Modelo Elétrico. Contrato de crédito automóvel para 36 meses, exemplo para "
    "Modelo Elétrico 115 kW, PVPR de 46.553,00€, PVP campanha de 35.553,00€, inclui "
    "despesas de legalização. Campanha válida até 31/08/2026."
)


def proposta(
    *,
    campaign_amount=35553.0,
    list_amount=46553.0,
    campaign_valid_until="2026-08-31",
    campaign_conditions: str | None = "Crédito 36 meses",
    evidence="PVPR de 46.553,00€, PVP campanha de 35.553,00€",
) -> dict:
    return {
        "offers": [
            {
                "kind": "list_price",
                "amount_eur": list_amount,
                "vat": "included",
                "customer": "private",
                "variant": "Base",
                "conditions": None,
                "validity": {"valid_from": None, "valid_until": None},
                "evidence": evidence,
                "derivation": None,
            },
            {
                "kind": "campaign_price",
                "amount_eur": campaign_amount,
                "vat": "included",
                "customer": "private",
                "variant": "Base",
                "conditions": campaign_conditions,
                "validity": {"valid_from": None, "valid_until": campaign_valid_until},
                "evidence": evidence,
                "derivation": None,
            },
        ]
    }


class BarreiraDaCitacao(unittest.TestCase):
    def test_proposta_inteiramente_suportada_pela_pagina_passa(self):
        self.assertEqual(verify(proposta(), PAGINA), [])

    def test_citacao_ausente_e_recusada(self):
        problemas = verify(proposta(evidence=""), PAGINA)
        self.assertTrue(any("sem citação" in p for p in problemas), problemas)

    def test_citacao_inventada_e_recusada(self):
        """O modelo parafraseia em vez de copiar: não entra."""
        problemas = verify(proposta(evidence="O carro custa trinta e cinco mil euros"), PAGINA)
        self.assertTrue(any("não aparece literalmente" in p for p in problemas), problemas)

    def test_preco_de_campanha_que_nao_esta_na_pagina_e_recusado(self):
        problemas = verify(proposta(campaign_amount=31999.0), PAGINA)
        self.assertTrue(any("31999" in p and "não aparece" in p for p in problemas), problemas)

    def test_pvp_que_nao_esta_na_pagina_e_recusado(self):
        problemas = verify(proposta(list_amount=44000.0), PAGINA)
        self.assertTrue(any("44000" in p and "não aparece" in p for p in problemas), problemas)

    def test_validade_que_nao_esta_na_pagina_e_recusada(self):
        problemas = verify(proposta(campaign_valid_until="2026-12-31"), PAGINA)
        self.assertTrue(any("2026-12-31" in p for p in problemas), problemas)

    def test_campanha_sem_condicoes_e_recusada(self):
        """AGENTS.md secção 8: uma campanha exige condições explícitas."""
        problemas = verify(proposta(campaign_conditions=None), PAGINA)
        self.assertTrue(any("condições" in p for p in problemas), problemas)

    def test_preco_negativo_ou_zero_e_recusado(self):
        for valor in (0, -100):
            with self.subTest(valor=valor):
                problemas = verify(proposta(campaign_amount=valor), PAGINA)
                self.assertTrue(problemas, f"{valor} devia ser recusado")

    def test_validade_fora_do_formato_iso_e_recusada(self):
        problemas = verify(proposta(campaign_valid_until="31/08/2026"), PAGINA)
        self.assertTrue(any("ISO" in p for p in problemas), problemas)


class FormatosDeData(unittest.TestCase):
    """As páginas portuguesas nunca escrevem a data em ISO."""

    def test_barra_ponto_e_extenso_sao_aceites(self):
        for texto in ("válida até 31/08/2026", "válida até 31-08-2026", "válida até 31 de agosto de 2026"):
            with self.subTest(texto=texto):
                self.assertTrue(date_appears("2026-08-31", texto, digits(texto)))

    def test_data_diferente_nao_e_aceite(self):
        texto = "válida até 30/09/2026"
        self.assertFalse(date_appears("2026-08-31", texto, digits(texto)))

    def test_pagina_sem_data_nao_e_aceite(self):
        texto = "campanha sem prazo publicado"
        self.assertFalse(date_appears("2026-08-31", texto, digits(texto)))


class EscolhaDaVariante(unittest.TestCase):
    """Aplicar a proposta à variante errada é pior do que não aplicar nada."""

    def modelo(self, *variantes) -> dict:
        return {"brand": "Marca", "model": "Modelo", "variants": list(variantes)}

    def variante(self, nome, campanha=None, pvp=None) -> dict:
        return {
            "name": nome,
            "pricing": {
                "offers": [
                    *([{"kind": "campaign_price", "amount_eur": campanha}] if campanha is not None else []),
                    *([{"kind": "list_price", "amount_eur": pvp}] if pvp is not None else []),
                ]
            },
        }

    def test_modelo_com_uma_variante_e_inequivoco(self):
        m = self.modelo(self.variante("Base"))
        self.assertIs(target_variant(m, proposta()), m["variants"][0])

    def test_com_varias_variantes_escolhe_a_que_tem_o_preco_extraido(self):
        m = self.modelo(self.variante("Base", pvp=29000), self.variante("Alta", campanha=35553.0))
        self.assertEqual(target_variant(m, proposta())["name"], "Alta")

    def test_com_varias_variantes_e_nenhum_preco_a_coincidir_nao_escolhe(self):
        m = self.modelo(self.variante("Base", pvp=29000), self.variante("Alta", pvp=31000))
        self.assertIsNone(target_variant(m, proposta()))

    def test_proposta_ambigua_nao_altera_o_catalogo(self):
        catalogo = {"models": [self.modelo(self.variante("Base", pvp=29000), self.variante("Alta", pvp=31000))]}
        antes = catalogo["models"][0]["variants"][0]["pricing"]["offers"]
        relatorio = apply_proposals(catalogo, [{**proposta(), "brand": "Marca", "model": "Modelo"}])
        self.assertTrue(any("NÃO APLICADA" in linha for linha in relatorio), relatorio)
        self.assertEqual(catalogo["models"][0]["variants"][0]["pricing"]["offers"], antes)

    def test_aplicar_nao_muda_catalogo_nem_datas(self):
        modelo = self.modelo(self.variante("Base"))
        modelo["data_sources"] = [{"type": "official_model", "url": "https://exemplo.pt", "verified_on": "2020-01-01"}]
        catalogo = {"models": [modelo]}
        apply_proposals(catalogo, [{**proposta(), "brand": "Marca", "model": "Modelo"}])
        self.assertNotIn("last_verified", catalogo["models"][0])
        self.assertEqual(catalogo["models"][0]["data_sources"][0]["verified_on"], "2020-01-01")


if __name__ == "__main__":
    unittest.main()

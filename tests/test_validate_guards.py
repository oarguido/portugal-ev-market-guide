"""Testes das defesas do validador que nenhum teste protegia.

Um teste de mutação mostrou quatro guardas que se podiam quebrar sem que a suíte
reparasse — e são precisamente as que apanharam defeitos reais neste projeto: o
mínimo de 5 KB deixou passar placeholders de 4,4 KB, a largura mínima existe
porque a única foto de exterior de um modelo tinha 307 px, a deteção de imagens
repetidas apanhou um MINI Aceman com a fotografia de um Fiat 500e, e a separação
entre códigos verificados e bloqueados existe porque o `make links` se dizia
verde com um terço das fontes por ler.

Guardas sem teste são guardas que alguém remove sem querer.
"""

import json
import math
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import rules
import validate_data
from validate_data import (
    BLOCKED_LINK_CODES,
    VERIFIED_LINK_CODES,
    duplicate_image_errors,
    validate_catalog,
)


def png(width: int, height: int, preenchimento: int = 0) -> bytes:
    """PNG mínimo com dimensões reais no IHDR e um recheio para dar tamanho."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk + b"\x00" * preenchimento


def catalogo(image_path: str) -> dict:
    """Catálogo mínimo que só falha por causa da fotografia."""
    today = validate_data.TODAY.isoformat()

    def oferta(amount=29_000, *, kind="list_price", classification="confirmed", conditions=None):
        evidence = f"PVP particular {amount:,.0f} €".replace(",", ".")
        return {
            "kind": kind,
            "classification": classification,
            "amount_eur": amount,
            "currency": "EUR",
            "source_url": "https://exemplo.pt/modelo",
            "source_authority": "manufacturer_or_importer_pt",
            "market": "PT",
            "variant": "Base",
            "conditions": conditions,
            "vat_included": True,
            "proof": {
                "url": "https://exemplo.pt/modelo",
                "source_url": "https://exemplo.pt/modelo",
                "authority": "manufacturer_or_importer_pt",
                "market": "PT",
                "audience": "particular",
                "variant": "Base",
                "vat_basis": "included",
                "literal_excerpt": evidence,
                "status": "verified",
                "source_type": "official_model",
                "recorded_on": today,
                "verified_on": today,
                "source_authority": "manufacturer_or_importer_pt",
                "customer": "private",
            },
            "derivation": None,
            "recorded_on": today,
            "verified_on": today,
            "customer": "private",
            "audience": "particular",
            "validity": {"valid_from": None, "valid_until": None},
            "valid_until": None,
            "vat": "included",
            "vat_status": "included",
            "evidence": evidence,
            "evidence_record": {
                "url": "https://exemplo.pt/modelo",
                "source_url": "https://exemplo.pt/modelo",
                "market": "PT",
                "recorded_on": today,
                "verified_on": today,
                "literal_excerpt": evidence,
            },
            "source_type": "official_model",
        }
    return {
        "schema_version": 3,
        "market": "PT",
        "currency": "EUR",
        "last_verified": today,
        "scope": {
            "powertrain": "BEV",
            "vehicle_type": "M1 passenger car",
            "condition": "new",
            "maximum_vat_inclusive_price_eur": validate_data.MAX_PRICE_EUR,
            "price_rule": "Só ofertas confirmadas provam limite.",
            "reference_price_policy": "Referências não contam.",
            "eligibility_statuses": ["confirmed_eligible", "potential_reference", "not_demonstrated"],
            "null_policy": "null significa por confirmar.",
        },
        "discovery_sources": [
            {
                "name": "Radar",
                "url": "https://exemplo.pt/radar",
                "type": "secondary_market_discovery",
                "verified_on": validate_data.TODAY.isoformat(),
                "usage_policy": "só descoberta",
                "known_limitations": ["inclui híbridos"],
            }
        ],
        "models": [
            {
                "brand": "Marca",
                "model": "Modelo",
                "release_year": 2025,
                "powertrain": "BEV",
                "segment": "Citadino",
                "availability_status": "available",
                "eligibility_status": "confirmed_eligible",
                "eligibility_tier": "confirmed_eligible",
                "eligibility_reason": "Existe oferta confirmada.",
                "official_link": "https://exemplo.pt/modelo",
                "image_path": image_path,
                "last_verified": validate_data.TODAY.isoformat(),
                "data_sources": [{"type": "official_model", "url": "https://exemplo.pt/modelo", "verified_on": validate_data.TODAY.isoformat()}],
                "dimensions": {
                    "length_mm": 4200,
                    "width_mm": 1780,
                    "height_mm": 1540,
                },
                "luggage_capacity": {
                    "boot_capacity_l": 350,
                    "frunk_capacity_l": None,
                },
                "pros": ["Bom desempenho", "Preço competitivo", "Boa garantia de bateria"],
                "cons": ["Mala modesta", "Carregamento AC 7 kW", "Materiais plásticos no interior"],
                "variants": [
                    {
                        "name": "Base",
                        "battery_capacity_kwh": 40,
                        "wltp_range_combined_km": 300,
                        "power_kw": 100,
                        "power_hp": 136,
                        "eligibility_status": "confirmed_eligible",
                        "eligibility_tier": "confirmed_eligible",
                        "battery_technology": {"chemistry": None, "generation": None, "architecture": None, "source_url": None, "verified_on": None},
                        "pricing": {
                            "offers": [oferta()],
                        },
                    }
                ],
            }
        ],
    }


class GuardasDaFotografia(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        # validate_data constrói os caminhos como ROOT / "web" / image_path.
        self.web = raiz / "web"
        (self.web / "img").mkdir(parents=True)
        patch = mock.patch.object(validate_data, "ROOT", raiz)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)
        self.rel = "img/foto.png"

    def escrever(self, dados: bytes) -> None:
        (self.web / "img" / "foto.png").write_bytes(dados)

    def test_fotografia_grande_e_larga_passa(self):
        self.escrever(png(1200, 800, preenchimento=20_000))
        self.assertEqual(validate_catalog(catalogo(self.rel)), [])

    def test_fotografia_abaixo_de_5kb_e_recusada(self):
        """4,4 KB era o tamanho dos placeholders da Stellantis."""
        self.escrever(png(1200, 800, preenchimento=1_000))
        erros = validate_catalog(catalogo(self.rel))
        self.assertTrue(any("ausente ou inválida" in e for e in erros), erros)

    def test_fotografia_estreita_e_recusada(self):
        """Existe porque a única foto de exterior do Changan tinha 307 px."""
        self.escrever(png(320, 200, preenchimento=20_000))
        erros = validate_catalog(catalogo(self.rel))
        self.assertTrue(any("px de largura" in e for e in erros), erros)

    def test_largura_exatamente_no_minimo_passa(self):
        self.escrever(png(validate_data.MIN_IMAGE_WIDTH, 400, preenchimento=20_000))
        self.assertEqual(validate_catalog(catalogo(self.rel)), [])


class FotografiaRepetida(unittest.TestCase):
    """Apanhou um MINI Aceman com a fotografia de um Fiat 500e cor-de-rosa."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self.web = raiz / "web"
        (self.web / "img").mkdir(parents=True)
        patch = mock.patch.object(validate_data, "ROOT", raiz)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def dois_modelos(self, bytes_a: bytes, bytes_b: bytes) -> dict:
        (self.web / "img" / "a.png").write_bytes(bytes_a)
        (self.web / "img" / "b.png").write_bytes(bytes_b)
        base = catalogo("img/a.png")
        segundo = json.loads(json.dumps(base["models"][0]))
        segundo["brand"], segundo["model"] = "Outra", "Outro"
        segundo["image_path"] = "img/b.png"
        base["models"].append(segundo)
        return base

    def test_dois_modelos_com_a_mesma_fotografia_sao_recusados(self):
        iguais = png(1200, 800, preenchimento=20_000)
        erros = duplicate_image_errors(self.dois_modelos(iguais, iguais))
        self.assertEqual(len(erros), 1, erros)
        self.assertIn("Marca Modelo", erros[0])
        self.assertIn("Outra Outro", erros[0])

    def test_fotografias_diferentes_passam(self):
        a = png(1200, 800, preenchimento=20_000)
        b = png(1200, 800, preenchimento=20_001)
        self.assertEqual(duplicate_image_errors(self.dois_modelos(a, b)), [])

    def test_fotografia_ausente_nao_conta_como_repetida(self):
        catalogo_sem = catalogo("nao/existe.png")
        self.assertEqual(duplicate_image_errors(catalogo_sem), [])


class CodigosDeLigacao(unittest.TestCase):
    """A separação existe porque o `make links` se dizia verde com 31 de 100
    fontes por ler. Um bloqueio não é uma verificação."""

    def test_verificado_e_bloqueado_nao_se_sobrepoem(self):
        self.assertEqual(VERIFIED_LINK_CODES & BLOCKED_LINK_CODES, set())

    def test_anti_bot_nunca_conta_como_verificado(self):
        for codigo in (403, 408, 429):
            with self.subTest(codigo=codigo):
                self.assertNotIn(codigo, VERIFIED_LINK_CODES)
                self.assertIn(codigo, BLOCKED_LINK_CODES)

    def test_apenas_respostas_lidas_contam_como_verificadas(self):
        self.assertEqual(VERIFIED_LINK_CODES, {200, 301, 302})


class RegrasDoCatalogo(unittest.TestCase):
    """Fixar os valores das regras, não só o mecanismo que as aplica.

    Os testes de obsolescência derivam as datas da própria constante
    (MAX_AGE_DAYS - 1, MAX_AGE_DAYS, MAX_AGE_DAYS + 1), por isso provam que o
    limite funciona mas adaptam-se a qualquer valor. Um teste de mutação
    mostrou-o: pôr a frescura em 400 dias não fazia falhar nada, e o catálogo
    passaria mais de um ano a apodrecer com a suíte verde.

    O mecanismo é testado noutro sítio. Aqui fixa-se a política, para que mudá-la
    seja uma decisão deliberada e não um acidente.
    """

    def test_o_limite_de_preco_e_40000_euros(self):
        """Secção 2 do AGENTS.md: até 40.000 € com IVA, não negociável."""
        self.assertEqual(rules.MAX_PRICE_EUR, 40_000)

    def test_a_frescura_e_de_45_dias(self):
        self.assertEqual(rules.MAX_AGE_DAYS, 45)

    def test_o_validador_usa_as_regras_partilhadas(self):
        """Uma cópia local da regra voltaria a divergir em silêncio."""
        self.assertIs(validate_data.MAX_PRICE_EUR, rules.MAX_PRICE_EUR)
        self.assertIs(validate_data.MAX_AGE_DAYS, rules.MAX_AGE_DAYS)

    def test_o_catalogo_declara_o_mesmo_limite_que_o_codigo(self):
        catalogo_real = validate_data.load_catalog()
        self.assertEqual(catalogo_real["scope"]["maximum_vat_inclusive_price_eur"], rules.MAX_PRICE_EUR)


class CamposObrigatorios(unittest.TestCase):
    """Verificações que sobrevivem a mutações por o catálogo real ser válido.

    Um teste que só corre sobre dados corretos nunca vê a verificação falhar: podia
    estar desligada. Estes usam fixtures deliberadamente inválidas.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self.web = raiz / "web"
        (self.web / "img").mkdir(parents=True)
        (self.web / "img" / "foto.png").write_bytes(png(1200, 800, preenchimento=20_000))
        patch = mock.patch.object(validate_data, "ROOT", raiz)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def base(self) -> dict:
        return catalogo("img/foto.png")

    def test_fonte_nao_oficial_e_recusada(self):
        c = self.base()
        c["models"][0]["data_sources"][0]["type"] = "imprensa"
        erros = validate_catalog(c)
        self.assertTrue(any("não é oficial" in e for e in erros), erros)

    def test_data_de_fonte_diferente_do_last_verified_e_recusada(self):
        c = self.base()
        c["models"][0]["data_sources"][0]["verified_on"] = "2020-01-01"
        erros = validate_catalog(c)
        self.assertTrue(any("data inconsistente" in e for e in erros), erros)

    def test_powertrain_que_nao_e_bev_e_recusado(self):
        c = self.base()
        c["models"][0]["powertrain"] = "PHEV"
        erros = validate_catalog(c)
        self.assertTrue(any("powertrain não é BEV" in e for e in erros), erros)

    def test_modelo_duplicado_e_recusado(self):
        c = self.base()
        c["models"].append(json.loads(json.dumps(c["models"][0])))
        erros = validate_catalog(c)
        self.assertTrue(any("duplicado" in e for e in erros), erros)

    def test_variante_duplicada_e_recusada(self):
        c = self.base()
        c["models"][0]["variants"].append(json.loads(json.dumps(c["models"][0]["variants"][0])))
        erros = validate_catalog(c)
        self.assertTrue(any("variante duplicada" in e for e in erros), erros)

    def test_preco_acima_do_limite_e_recusado(self):
        c = self.base()
        c["models"][0]["variants"][0]["pricing"]["offers"][0]["amount_eur"] = rules.MAX_PRICE_EUR + 1
        erros = validate_catalog(c)
        self.assertTrue(any("eligibility_tier" in e for e in erros), erros)

    def test_campanha_sem_condicoes_e_recusada(self):
        c = self.base()
        campaign = json.loads(json.dumps(c["models"][0]["variants"][0]["pricing"]["offers"][0]))
        campaign.update(kind="campaign_price", amount_eur=30_000, conditions=None)
        c["models"][0]["variants"][0]["pricing"]["offers"].append(campaign)
        erros = validate_catalog(c)
        self.assertTrue(any("sem condições" in e for e in erros), erros)

    def test_campanha_superior_ao_pvp_e_recusada(self):
        c = self.base()
        pricing = c["models"][0]["variants"][0]["pricing"]
        campaign = json.loads(json.dumps(pricing["offers"][0]))
        campaign.update(kind="campaign_price", amount_eur=30_001, conditions="Financiamento para particulares", evidence="Campanha 30.001 €")
        campaign["proof"]["literal_excerpt"] = campaign["evidence"]
        campaign["evidence_record"]["literal_excerpt"] = campaign["evidence"]
        pricing["offers"][0]["amount_eur"] = 30_000
        pricing["offers"].append(campaign)
        erros = validate_catalog(c)
        self.assertTrue(any("não pode exceder o PVP" in e for e in erros), erros)

    def test_preco_infinito_nan_negativo_ou_booleano_e_recusado(self):
        for valor in (math.inf, math.nan, -1, True):
            with self.subTest(valor=valor):
                c = self.base()
                c["models"][0]["variants"][0]["pricing"]["offers"][0]["amount_eur"] = valor
                erros = validate_catalog(c)
                self.assertTrue(any("amount_eur" in e for e in erros), erros)

    def test_zero_e_nao_negativo_mas_nao_elegivel(self):
        c = self.base()
        c["models"][0]["variants"][0]["pricing"]["offers"][0]["amount_eur"] = 0
        erros = validate_catalog(c)
        self.assertTrue(any("amount_eur" in e for e in erros), erros)

    def test_validade_de_campanha_tem_formato_explicito_ou_null(self):
        base = self.base()
        campaign = json.loads(json.dumps(base["models"][0]["variants"][0]["pricing"]["offers"][0]))
        campaign.update(kind="campaign_price", amount_eur=28_000, conditions="Financiamento para particulares", evidence="Campanha 28.000 €")
        campaign["proof"]["literal_excerpt"] = campaign["evidence"]
        campaign["evidence_record"]["literal_excerpt"] = campaign["evidence"]
        base["models"][0]["variants"][0]["pricing"]["offers"].append(campaign)
        self.assertEqual(validate_catalog(base), [])
        for expiry in ("", "31/08/2026", "2026-02-30"):
            with self.subTest(expiry=expiry):
                c = self.base()
                campaign = json.loads(json.dumps(c["models"][0]["variants"][0]["pricing"]["offers"][0]))
                campaign.update(kind="campaign_price", amount_eur=28_000, conditions="Financiamento para particulares", evidence="Campanha 28.000 €")
                campaign["proof"]["literal_excerpt"] = campaign["evidence"]
                campaign["evidence_record"]["literal_excerpt"] = campaign["evidence"]
                campaign["validity"] = {"valid_from": None, "valid_until": expiry}
                campaign["valid_until"] = expiry
                c["models"][0]["variants"][0]["pricing"]["offers"].append(campaign)
                erros = validate_catalog(c)
                self.assertTrue(any("validity.valid_until" in e for e in erros), erros)

    def test_condicoes_de_campanha_tem_de_ser_texto_material(self):
        for conditions in (None, "", "   ", "N/A", "por confirmar", 123):
            with self.subTest(conditions=conditions):
                c = self.base()
                campaign = json.loads(json.dumps(c["models"][0]["variants"][0]["pricing"]["offers"][0]))
                campaign.update(kind="campaign_price", amount_eur=30_000, conditions=conditions, evidence="Campanha 30.000 €")
                campaign["proof"]["literal_excerpt"] = campaign["evidence"]
                campaign["evidence_record"]["literal_excerpt"] = campaign["evidence"]
                c["models"][0]["variants"][0]["pricing"]["offers"].append(campaign)
                erros = validate_catalog(c)
                self.assertTrue(any("condições materiais" in e for e in erros), erros)

    def test_fonte_sem_https_e_recusada(self):
        c = self.base()
        c["models"][0]["data_sources"][0]["url"] = "http://exemplo.pt/modelo"
        erros = validate_catalog(c)
        self.assertTrue(any("HTTPS" in e for e in erros), erros)


class ConcessionariosObrigatorios(unittest.TestCase):
    def base_dealers(self, **alteracoes) -> dict:
        dealer = {
            "brand": "Marca",
            "name": "Stand",
            "address": "Rua A",
            "postal_code": "4000-001",
            "locality": "Porto",
            "phone": "220000000",
            "email": "a@b.pt",
            "official_url": "https://exemplo.pt/stand",
            "maps_url": "https://maps.example.com/x",
            "services": ["sales"],
            "verified_on": validate_data.TODAY.isoformat(),
        }
        dealer.update(alteracoes)
        return {"schema_version": 1, "market": "PT", "reference_location": "São Mamede de Infesta, Matosinhos", "dealers": [dealer]}

    def test_stand_valido_passa(self):
        self.assertEqual(validate_data.validate_dealers(catalogo("x"), self.base_dealers()), [])

    def test_stand_que_nao_vende_novos_e_recusado(self):
        erros = validate_data.validate_dealers(catalogo("x"), self.base_dealers(services=["service"]))
        self.assertTrue(any("vender veículos novos" in e for e in erros), erros)

    def test_marca_sem_stand_e_recusada(self):
        vazio = {"schema_version": 1, "market": "PT", "reference_location": "São Mamede de Infesta, Matosinhos", "dealers": []}
        erros = validate_data.validate_dealers(catalogo("x"), vazio)
        self.assertTrue(any("sem concessionário" in e for e in erros), erros)

    def test_stand_de_marca_inexistente_e_recusado(self):
        erros = validate_data.validate_dealers(catalogo("x"), self.base_dealers(brand="Inexistente"))
        self.assertTrue(any("sem marca ativa" in e for e in erros), erros)


class TecnologiaDaBateriaOpcional(unittest.TestCase):
    """Campos documentados podem entrar quando provados, sem valores inventados."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self.web = raiz / "web"
        (self.web / "img").mkdir(parents=True)
        (self.web / "img" / "foto.png").write_bytes(png(1200, 800, preenchimento=20_000))
        patch = mock.patch.object(validate_data, "ROOT", raiz)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_tecnologia_documentada_valida_passes(self):
        c = catalogo("img/foto.png")
        c["models"][0]["variants"][0]["battery_technology"] = {
            "chemistry": "LFP",
            "generation": "Blade Battery",
            "architecture": "cell-to-pack",
            "source_url": "https://exemplo.pt/bateria",
            "verified_on": validate_data.TODAY.isoformat(),
        }
        self.assertEqual(validate_catalog(c), [])

    def test_tecnologia_desconhecida_pode_ser_null_ou_ausente(self):
        c = catalogo("img/foto.png")
        self.assertEqual(validate_catalog(c), [])

    def test_tecnologia_com_tipo_invalido_e_recusada(self):
        c = catalogo("img/foto.png")
        c["models"][0]["variants"][0]["battery_technology"]["chemistry"] = 123
        erros = validate_catalog(c)
        self.assertTrue(any("battery_technology.chemistry" in e for e in erros), erros)


class NovosCamposEsquema(unittest.TestCase):
    """Testes de guarda para dimensões, capacidade de bagagem, pros e cons."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self.web = raiz / "web"
        (self.web / "img").mkdir(parents=True)
        (self.web / "img" / "foto.png").write_bytes(png(1200, 800, preenchimento=20_000))
        patch = mock.patch.object(validate_data, "ROOT", raiz)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def base(self) -> dict:
        return catalogo("img/foto.png")

    def test_dimensoes_invalidas_sao_recusadas(self):
        c = self.base()
        c["models"][0]["dimensions"] = "não é objeto"
        erros = validate_catalog(c)
        self.assertTrue(any("'dimensions' tem de ser um objeto" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["dimensions"]["length_mm"] = 0
        erros = validate_catalog(c)
        self.assertTrue(any("dimensions.length_mm tem de ser um inteiro positivo" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["dimensions"]["width_mm"] = -10
        erros = validate_catalog(c)
        self.assertTrue(any("dimensions.width_mm tem de ser um inteiro positivo" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["dimensions"]["height_mm"] = "1540"
        erros = validate_catalog(c)
        self.assertTrue(any("dimensions.height_mm tem de ser um inteiro positivo" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["dimensions"]["length_mm"] = True
        erros = validate_catalog(c)
        self.assertTrue(any("dimensions.length_mm tem de ser um inteiro positivo" in e for e in erros), erros)

    def test_capacidade_bagageira_invalida_e_recusada(self):
        c = self.base()
        c["models"][0]["luggage_capacity"] = []
        erros = validate_catalog(c)
        self.assertTrue(any("'luggage_capacity' tem de ser um objeto" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["luggage_capacity"]["boot_capacity_l"] = 0
        erros = validate_catalog(c)
        self.assertTrue(any("luggage_capacity.boot_capacity_l tem de ser um inteiro positivo" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["luggage_capacity"]["frunk_capacity_l"] = -1
        erros = validate_catalog(c)
        self.assertTrue(any("luggage_capacity.frunk_capacity_l tem de ser um inteiro não-negativo ou null" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["luggage_capacity"]["frunk_capacity_l"] = "25"
        erros = validate_catalog(c)
        self.assertTrue(any("luggage_capacity.frunk_capacity_l tem de ser um inteiro não-negativo ou null" in e for e in erros), erros)

    def test_frunk_valido_com_inteiro_e_null_passam(self):
        c = self.base()
        c["models"][0]["luggage_capacity"]["frunk_capacity_l"] = 0
        self.assertEqual(validate_catalog(c), [])

        c = self.base()
        c["models"][0]["luggage_capacity"]["frunk_capacity_l"] = 25
        self.assertEqual(validate_catalog(c), [])

    def test_pros_e_cons_invalidos_sao_recusados(self):
        c = self.base()
        c["models"][0]["pros"] = []
        erros = validate_catalog(c)
        self.assertTrue(any("'pros' tem de ser uma lista não vazia" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["pros"] = ["Bom desempenho", "Preço competitivo"]
        erros = validate_catalog(c)
        self.assertTrue(any("'pros' tem de conter entre 3 e 5 elementos" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["cons"] = ["Um", "Dois", "Três", "Quatro", "Cinco", "Seis"]
        erros = validate_catalog(c)
        self.assertTrue(any("'cons' tem de conter entre 3 e 5 elementos" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["cons"] = ["   ", "Segundo", "Terceiro"]
        erros = validate_catalog(c)
        self.assertTrue(any("item em 'cons' tem de ser uma string não vazia" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["pros"] = [123, "Segundo", "Terceiro"]
        erros = validate_catalog(c)
        self.assertTrue(any("item em 'pros' tem de ser uma string não vazia" in e for e in erros), erros)

        c = self.base()
        c["models"][0]["cons"] = None
        erros = validate_catalog(c)
        self.assertTrue(any("'cons' tem de ser uma lista não vazia" in e for e in erros), erros)


if __name__ == "__main__":
    unittest.main()

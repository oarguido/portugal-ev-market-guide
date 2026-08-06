"""Fixtures do contrato v3 enquanto catálogo canónico aguarda migração."""

from __future__ import annotations

import copy
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import compile_data
import refresh_prices
import validate_data
from expire_campaigns import expire_catalog
from refresh_prices import apply_proposals, normalize_proposal, verify
from rules import variant_eligibility_tier


def png(width: int = 1200, height: int = 800, fill: int = 20_000) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    return b"\x89PNG\r\n\x1a\n" + chunk + b"\x00" * fill


def offer(
    *,
    kind: str = "list_price",
    amount: float = 30_000,
    classification: str = "confirmed",
    status: str = "verified",
    customer: str = "private",
    vat: str | None = "included",
    variant: str = "Base",
    evidence: str | None = "PVP particular 30.000 € com IVA",
    verified_on: str | None = None,
    valid_until: str | None = None,
) -> dict:
    verified_on = verified_on or validate_data.TODAY.isoformat()
    return {
        "kind": kind,
        "classification": classification,
        "amount_eur": amount,
        "currency": "EUR",
        "source_url": "https://marca.pt/precos",
        "source_authority": "manufacturer_or_importer_pt",
        "market": "PT",
        "variant": variant,
        "conditions": "Campanha para particulares" if kind == "campaign_price" else None,
        "vat_included": True if vat in {"included", "derived"} else None,
        "proof": {
            "url": "https://marca.pt/precos",
            "source_url": "https://marca.pt/precos",
            "authority": "manufacturer_or_importer_pt",
            "market": "PT",
            "audience": "particular" if customer == "private" else "unknown",
            "variant": variant,
            "vat_basis": vat if vat in {"included", "excluded", "derived"} else "unknown",
            "literal_excerpt": evidence,
            "status": status,
            "source_type": "official_price_sheet",
            "recorded_on": validate_data.TODAY.isoformat(),
            "verified_on": verified_on,
            "source_authority": "manufacturer_or_importer_pt",
            "customer": customer,
        },
        "derivation": None,
        "recorded_on": validate_data.TODAY.isoformat(),
        "verified_on": verified_on,
        "customer": customer,
        "audience": "particular" if customer == "private" else "unknown",
        "validity": {"valid_from": None, "valid_until": valid_until},
        "valid_until": valid_until,
        "vat": vat,
        "vat_status": vat if vat in {"included", "excluded", "derived"} else "unknown",
        "evidence": evidence,
        "evidence_record": {
            "url": "https://marca.pt/precos",
            "source_url": "https://marca.pt/precos",
            "market": "PT",
            "recorded_on": validate_data.TODAY.isoformat(),
            "verified_on": verified_on,
            "literal_excerpt": evidence,
        },
        "source_type": "official_price_sheet",
    }


def catalog_fixture(*, pricing: dict | None = None, eligible: bool = True) -> dict:
    today = validate_data.TODAY.isoformat()
    return {
        "schema_version": 3,
        "market": "PT",
        "currency": "EUR",
        "last_verified": today,
        "scope": {
            "powertrain": "BEV",
            "vehicle_type": "M1 passenger car",
            "condition": "new",
            "maximum_vat_inclusive_price_eur": 40_000,
            "price_rule": "Só ofertas confirmadas podem provar o limite.",
            "reference_price_policy": "Referências não contam para elegibilidade.",
            "eligibility_statuses": ["confirmed_eligible", "potential_reference", "not_demonstrated"],
            "null_policy": "null significa por confirmar.",
        },
        "discovery_sources": [
            {
                "name": "Radar",
                "url": "https://radar.pt/ev",
                "type": "secondary_market_discovery",
                "verified_on": today,
                "usage_policy": "só descoberta",
                "known_limitations": ["não é fonte final"],
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
                "eligibility_status": "confirmed_eligible" if eligible else "potential_reference",
                "eligibility_tier": "confirmed_eligible" if eligible else "potential_reference",
                "eligibility_reason": "Existe prova" if eligible else "Só existe referência",
                "official_link": "https://marca.pt/modelo",
                "image_path": "img/modelo.png",
                "last_verified": today,
                "data_sources": [
                    {"type": "official_price_sheet", "url": "https://marca.pt/precos", "verified_on": today}
                ],
                "dimensions": {"length_mm": 4200, "width_mm": 1780, "height_mm": 1500},
                "luggage_capacity": {"boot_capacity_l": 350, "frunk_capacity_l": None},
                "pros": ["Um", "Dois", "Três"],
                "cons": ["Quatro", "Cinco", "Seis"],
                "variants": [
                    {
                        "name": "Base",
                        "battery_capacity_kwh": 40,
                        "wltp_range_combined_km": 300,
                        "power_kw": 100,
                        "power_hp": 136,
                        "eligibility_status": "confirmed_eligible" if eligible else "potential_reference",
                        "eligibility_tier": "confirmed_eligible" if eligible else "potential_reference",
                        "battery_technology": {"chemistry": None, "generation": None, "architecture": None, "source_url": None, "verified_on": None},
                        "pricing": pricing or {"offers": [offer()]},
                    }
                ],
            }
        ],
    }


class SchemaV3ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "web" / "img").mkdir(parents=True)
        (root / "web" / "img" / "modelo.png").write_bytes(png())
        self.root_patch = mock.patch.object(validate_data, "ROOT", root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_confirmed_offer_v3_passes_and_proves_tier(self):
        catalog = catalog_fixture()
        self.assertEqual(validate_data.validate_catalog(catalog), [])
        variant = catalog["models"][0]["variants"][0]
        self.assertEqual(variant_eligibility_tier(variant, validate_data.TODAY), "confirmed_eligible")

    def test_v2_is_rejected(self):
        catalog = catalog_fixture()
        catalog["schema_version"] = 2
        errors = validate_data.validate_catalog(catalog)
        self.assertTrue(any("schema_version tem de ser 3" in error for error in errors), errors)

    def test_reference_legacy_passes_but_is_not_eligible(self):
        reference = offer(classification="reference", status="legacy_unverified", customer="unknown", vat=None, evidence=None)
        reference["proof"]["verified_on"] = None
        reference["verified_on"] = None
        reference["evidence_record"]["verified_on"] = None
        reference["legacy_unverified"] = True
        catalog = catalog_fixture(pricing={"offers": [reference]}, eligible=False)
        self.assertEqual(validate_data.validate_catalog(catalog), [])
        self.assertEqual(variant_eligibility_tier(catalog["models"][0]["variants"][0], validate_data.TODAY), "potential_reference")

    def test_current_reference_keeps_verified_date_but_never_becomes_confirmed(self):
        reference = offer(classification="reference", status="verified", customer="unknown", vat=None, evidence="Preço indicativo 30.000 €")
        catalog = catalog_fixture(pricing={"offers": [reference]}, eligible=False)
        self.assertEqual(validate_data.validate_catalog(catalog), [])
        self.assertEqual(catalog["models"][0]["eligibility_tier"], "potential_reference")

    def test_not_demonstrated_variant_may_have_zero_offers(self):
        catalog = catalog_fixture(pricing={"offers": []}, eligible=False)
        model = catalog["models"][0]
        variant = model["variants"][0]
        model["eligibility_status"] = model["eligibility_tier"] = "not_demonstrated"
        model["eligibility_reason"] = "Não existe oferta demonstrável."
        variant["eligibility_status"] = variant["eligibility_tier"] = "not_demonstrated"
        self.assertEqual(validate_data.validate_catalog(catalog), [])

    def test_reference_campaign_may_omit_incomplete_terms(self):
        reference = offer(
            kind="campaign_price",
            classification="reference",
            status="legacy_unverified",
            customer="unknown",
            vat="excluded",
            evidence=None,
        )
        reference["conditions"] = None
        reference["proof"]["verified_on"] = None
        reference["verified_on"] = None
        reference["evidence_record"]["verified_on"] = None
        reference["legacy_unverified"] = True
        catalog = catalog_fixture(pricing={"offers": [reference]}, eligible=False)
        self.assertEqual(validate_data.validate_catalog(catalog), [])

    def test_excluded_vat_status_is_literal_and_preserved(self):
        reference = offer(
            classification="reference",
            status="verified",
            customer="unknown",
            vat="excluded",
            evidence="Preço 30.000 € sem IVA",
        )
        self.assertEqual(reference["vat_status"], "excluded")
        self.assertEqual(reference["proof"]["vat_basis"], "excluded")
        catalog = catalog_fixture(pricing={"offers": [reference]}, eligible=False)
        self.assertEqual(validate_data.validate_catalog(catalog), [])

    def test_confirmed_evidence_cannot_match_numeric_prefix_only(self):
        catalog = catalog_fixture()
        offer_data = catalog["models"][0]["variants"][0]["pricing"]["offers"][0]
        offer_data["evidence"] = "PVP particular 130.000 € com IVA"
        offer_data["proof"]["literal_excerpt"] = offer_data["evidence"]
        offer_data["evidence_record"]["literal_excerpt"] = offer_data["evidence"]
        errors = validate_data.validate_catalog(catalog)
        self.assertTrue(any("evidence não contém" in error for error in errors), errors)
        self.assertEqual(variant_eligibility_tier(catalog["models"][0]["variants"][0], validate_data.TODAY), "not_demonstrated")

    def test_matrix_rejects_source_market_variant_and_literal_failures(self):
        catalog = catalog_fixture()
        current = catalog["models"][0]["variants"][0]["pricing"]["offers"][0]
        current["proof"]["market"] = "ES"
        current["variant"] = "Outra"
        current["evidence"] = "Preço sem montante"
        errors = validate_data.validate_catalog(catalog)
        self.assertTrue(any("proof.market" in error for error in errors), errors)
        self.assertTrue(any("variant tem de coincidir" in error for error in errors), errors)
        self.assertTrue(any("evidence não contém" in error for error in errors), errors)

    def test_campaign_cannot_exceed_list_price(self):
        catalog = catalog_fixture(
            pricing={
                "offers": [
                    offer(kind="list_price", amount=30_000),
                    offer(kind="campaign_price", amount=30_001, evidence="Campanha 30.001 €"),
                ]
            }
        )
        errors = validate_data.validate_catalog(catalog)
        self.assertTrue(any("campanha não pode exceder" in error for error in errors), errors)

    def test_exact_vat_derivation_is_required(self):
        derived = offer(amount=33_000, vat="derived", evidence="Preço nacional 26.829,27 € + IVA")
        derived["derivation"] = {
            "method": "add_vat",
            "source_amount_eur": 26_829.27,
            "vat_rate": 0.23,
            "result_amount_eur": 33_000,
        }
        catalog = catalog_fixture(pricing={"offers": [derived]})
        errors = validate_data.validate_catalog(catalog)
        self.assertTrue(any("derivação de IVA" in error for error in errors), errors)

    def test_expired_confirmed_offer_changes_tier_only_when_reference_exists(self):
        expired = offer(kind="campaign_price", amount=29_000, evidence="Campanha 29.000 €", valid_until="2020-01-01")
        reference = offer(classification="reference", status="legacy_unverified", customer="unknown", vat="excluded", evidence=None)
        variant = {"name": "Base", "eligibility_tier": "confirmed_eligible", "pricing": {"offers": [expired, reference]}}
        catalog = catalog_fixture(pricing=variant["pricing"])
        catalog["models"][0]["variants"][0]["eligibility_tier"] = "potential_reference"
        dealer = {"dealers": [{"brand": "Marca"}]}
        report = expire_catalog(catalog, dealer, validate_data.TODAY)
        kept = catalog["models"][0]["variants"][0]
        self.assertEqual(len(kept["pricing"]["offers"]), 2)
        self.assertEqual(kept["eligibility_tier"], "potential_reference")
        self.assertEqual(catalog["models"][0]["eligibility_tier"], "potential_reference")
        self.assertTrue(any("OFERTA EXPIRADA" in line for line in report), report)

    def test_expiry_keeps_confirmed_tier_when_reference_coexists(self):
        current = offer(kind="list_price", amount=30_000)
        expired = offer(kind="campaign_price", amount=29_000, evidence="Campanha 29.000 €", valid_until="2020-01-01")
        reference = offer(classification="reference", status="legacy_unverified", customer="unknown", vat="excluded", evidence=None)
        reference["conditions"] = None
        reference["proof"]["verified_on"] = None
        reference["verified_on"] = None
        reference["evidence_record"]["verified_on"] = None
        reference["legacy_unverified"] = True
        catalog = catalog_fixture(pricing={"offers": [current, expired, reference]})
        expire_catalog(catalog, {"dealers": []}, validate_data.TODAY)
        variant = catalog["models"][0]["variants"][0]
        self.assertEqual(variant["eligibility_tier"], "confirmed_eligible")
        self.assertEqual(catalog["models"][0]["eligibility_tier"], "confirmed_eligible")


class FailClosedCompilationTests(unittest.TestCase):
    def test_invalid_catalogue_does_not_overwrite_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "car_data.js"
            bundle.write_text("old bundle", encoding="utf-8")
            invalid = {"schema_version": 2, "models": []}
            dealers = {"schema_version": 1, "market": "PT", "reference_location": "São Mamede de Infesta, Matosinhos", "dealers": []}
            with (
                mock.patch.object(compile_data, "load_catalog", return_value=invalid),
                mock.patch.object(compile_data, "load_dealers", return_value=dealers),
                mock.patch.object(compile_data, "BUNDLE_PATH", bundle),
                mock.patch.object(validate_data, "ROOT", root),
                self.assertRaisesRegex(ValueError, "bundle não foi escrito"),
            ):
                compile_data.compile_data()
            self.assertEqual(bundle.read_text(encoding="utf-8"), "old bundle")


class PriceProposalOnlyTests(unittest.TestCase):
    def test_apply_compatibility_api_never_mutates_catalogue(self):
        catalog = {"models": [{"brand": "Marca", "model": "Modelo"}]}
        before = copy.deepcopy(catalog)
        result = apply_proposals(catalog, [{"brand": "Marca", "model": "Modelo"}])
        self.assertEqual(catalog, before)
        self.assertIn("NÃO APLICADA", result[0])

    def test_page_evidence_still_requires_literal_amount(self):
        proposal = {
            "offers": [
                {
                    "kind": "list_price",
                    "amount_eur": 30_000,
                    "vat": "included",
                    "customer": "private",
                    "evidence": "PVP particular 31.000 €",
                }
            ]
        }
        self.assertTrue(any("não aparece" in error for error in verify(proposal, "PVP particular 31.000 €")))

    def test_reference_campaign_without_conditions_is_accepted_for_review(self):
        proposal = {
            "offers": [{
                "kind": "campaign_price",
                "classification": "reference",
                "amount_eur": 30_000,
                "vat": "excluded",
                "customer": "unknown",
                "variant": "Base",
                "conditions": None,
                "validity": {"valid_from": None, "valid_until": None},
                "evidence": "Campanha 30.000 €",
                "derivation": None,
            }]
        }
        self.assertEqual(verify(proposal, "Campanha 30.000 €"), [])

    def test_refresh_normalization_never_promotes_proposal(self):
        model = {
            "brand": "Marca",
            "model": "Modelo",
            "data_sources": [{"type": "official_price_sheet", "url": "https://marca.pt/precos"}],
        }
        proposal = {
            "offers": [{
                "kind": "list_price",
                "amount_eur": 30_000,
                "vat": "included",
                "customer": "private",
                "variant": "Base",
                "conditions": None,
                "validity": {"valid_from": None, "valid_until": None},
                "evidence": "PVP particular 30.000 € com IVA",
                "derivation": None,
            }]
        }
        normalized = normalize_proposal(proposal, model, "https://marca.pt/precos")
        self.assertEqual(normalized["offers"][0]["classification"], "reference")
        self.assertEqual(normalized["offers"][0]["customer"], "private")

    def test_customer_enum_uses_company_not_business(self):
        proposal = {
            "offers": [{
                "kind": "list_price",
                "amount_eur": 30_000,
                "vat": "excluded",
                "customer": "company",
                "variant": "Base",
                "conditions": None,
                "validity": {"valid_from": None, "valid_until": None},
                "evidence": "PVP empresa 30.000 €",
                "derivation": None,
            }]
        }
        self.assertEqual(verify(proposal, "PVP empresa 30.000 €"), [])
        proposal["offers"][0]["customer"] = "business"
        self.assertTrue(verify(proposal, "PVP empresa 30.000 €"))

    def test_main_apply_flag_writes_proposal_but_not_catalogue(self):
        catalog = {
            "models": [
                {
                    "brand": "Marca",
                    "model": "Modelo",
                    "data_sources": [{"type": "official_price_sheet", "url": "https://marca.pt/precos"}],
                    "variants": [{"name": "Base"}],
                }
            ]
        }
        proposal = {
            "offers": [{
                "kind": "list_price",
                "amount_eur": 30_000,
                "vat": "included",
                "customer": "private",
                "variant": "Base",
                "conditions": None,
                "validity": {"valid_from": None, "valid_until": None},
                "evidence": "PVP particular 30.000 €",
                "derivation": None,
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog_path = root / "pt_market.json"
            proposals_path = root / "price_proposals.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            with (
                mock.patch.object(refresh_prices, "CATALOG_PATH", catalog_path),
                mock.patch.object(refresh_prices, "PROPOSALS_PATH", proposals_path),
                mock.patch.object(refresh_prices, "browser_text", return_value="PVP particular 30.000 €"),
                mock.patch.object(refresh_prices, "extract", return_value=proposal),
                mock.patch("sys.argv", ["refresh_prices.py", "--apply"]),
            ):
                self.assertEqual(refresh_prices.main(), 0)
            self.assertEqual(json.loads(catalog_path.read_text(encoding="utf-8")), catalog)
            self.assertTrue(json.loads(proposals_path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()

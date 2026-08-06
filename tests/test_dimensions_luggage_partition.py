"""Category-partition and boundary value test suite for vehicle dimensions and luggage capacity.

Requirements tested:
- R2. Schema Expansion & Data Enrichment (dimensions mm, boot L, frunk L)
- Schema contract: dimensions { length_mm > 0, width_mm > 0, height_mm > 0 }
- Schema contract: luggage_capacity { boot_capacity_l > 0, frunk_capacity_l >= 0 or None }

Derivation of Expected Output:
- Specifications in PROJECT.md Interface Contracts and AGENTS.md § 8.
- Category partitions for Dimensions (mm):
    Length:
      - Micro/City: 1 <= length_mm < 3800
      - Compact: 3800 <= length_mm <= 4400
      - Large: length_mm > 4400
    Width:
      - Narrow: 1 <= width_mm < 1750
      - Medium: 1750 <= width_mm <= 1850
      - Wide: width_mm > 1850
    Height:
      - Low: 1 <= height_mm < 1500
      - Medium: 1500 <= height_mm <= 1650
      - Tall: height_mm > 1650
- Category partitions for Luggage Volume (L):
    Boot:
      - Small: 1 <= boot_capacity_l < 300
      - Medium: 300 <= boot_capacity_l <= 450
      - Large: boot_capacity_l > 450
    Frunk:
      - None/Null: None
      - Zero: 0
      - Small: 1 <= frunk_capacity_l <= 30
      - Large: frunk_capacity_l > 30
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_data
from validate_data import validate_catalog


def build_test_catalog(dimensions=None, luggage_capacity=None, pros=None, cons=None) -> dict:
    """Helper to build a valid catalog fixture with customizable dimensions and luggage."""
    if dimensions is None:
        dimensions = {"length_mm": 4200, "width_mm": 1780, "height_mm": 1540}
    if luggage_capacity is None:
        luggage_capacity = {"boot_capacity_l": 350, "frunk_capacity_l": None}
    if pros is None:
        pros = ["Design moderno", "Excelente consumo", "Boa autonomia WLTP"]
    if cons is None:
        cons = ["Carregamento AC limitado", "Mala modesta", "Visibilidade traseira reduzida"]

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
                "brand": "MarcaTest",
                "model": "ModeloTest",
                "release_year": 2025,
                "powertrain": "BEV",
                "segment": "Compacto",
                "availability_status": "available",
                "eligibility_status": "confirmed_eligible",
                "eligibility_tier": "confirmed_eligible",
                "eligibility_reason": "Existe oferta confirmada.",
                "official_link": "https://exemplo.pt/modelo",
                "image_path": "img/foto.png",
                "last_verified": validate_data.TODAY.isoformat(),
                "data_sources": [
                    {
                        "type": "official_model",
                        "url": "https://exemplo.pt/modelo",
                        "verified_on": validate_data.TODAY.isoformat(),
                    }
                ],
                "dimensions": dimensions,
                "luggage_capacity": luggage_capacity,
                "pros": pros,
                "cons": cons,
                "variants": [
                    {
                        "name": "Standard",
                        "battery_capacity_kwh": 50.0,
                        "wltp_range_combined_km": 350,
                        "power_kw": 110,
                        "power_hp": 150,
                        "eligibility_status": "confirmed_eligible",
                        "eligibility_tier": "confirmed_eligible",
                        "battery_technology": {
                            "chemistry": None,
                            "generation": None,
                            "architecture": None,
                            "source_url": None,
                            "verified_on": None,
                        },
                        "pricing": {
                            "offers": [{
                                "kind": "list_price",
                                "classification": "confirmed",
                                "amount_eur": 32000.0,
                                "currency": "EUR",
                                "source_url": "https://exemplo.pt/modelo",
                                "source_authority": "manufacturer_or_importer_pt",
                                "market": "PT",
                                "source_type": "official_model",
                                "vat": "included",
                                "vat_status": "included",
                                "vat_included": True,
                                "customer": "private",
                                "audience": "particular",
                                "variant": "Standard",
                                "conditions": None,
                                "validity": {"valid_from": None, "valid_until": None},
                                "valid_until": None,
                                "proof": {
                                    "url": "https://exemplo.pt/modelo",
                                    "status": "verified",
                                    "authority": "manufacturer_or_importer_pt",
                                    "source_authority": "manufacturer_or_importer_pt",
                                    "source_url": "https://exemplo.pt/modelo",
                                    "source_type": "official_model",
                                    "market": "PT",
                                    "audience": "particular",
                                    "customer": "private",
                                    "variant": "Standard",
                                    "vat_basis": "included",
                                    "recorded_on": today,
                                    "verified_on": today,
                                    "literal_excerpt": "PVP particular 32.000 €",
                                },
                                "evidence": "PVP particular 32.000 €",
                                "evidence_record": {
                                    "url": "https://exemplo.pt/modelo",
                                    "source_url": "https://exemplo.pt/modelo",
                                    "market": "PT",
                                    "recorded_on": today,
                                    "verified_on": today,
                                    "literal_excerpt": "PVP particular 32.000 €",
                                },
                                "derivation": None,
                                "recorded_on": today,
                                "verified_on": today,
                            }],
                        },
                    }
                ],
            }
        ],
    }


def categorize_length(length_mm: int) -> str:
    """Categorize length into micro, compact, or large."""
    if length_mm < 3800:
        return "Micro / Citadino"
    elif length_mm <= 4400:
        return "Compacto"
    else:
        return "Familiar / Grande"


def categorize_width(width_mm: int) -> str:
    """Categorize width into narrow, medium, or wide."""
    if width_mm < 1750:
        return "Estreito"
    elif width_mm <= 1850:
        return "Médio"
    else:
        return "Largo"


def categorize_height(height_mm: int) -> str:
    """Categorize height into low, medium, or tall."""
    if height_mm < 1500:
        return "Baixo"
    elif height_mm <= 1650:
        return "Médio"
    else:
        return "Alto"


def categorize_boot(boot_l: int) -> str:
    """Categorize boot volume into small, medium, or large."""
    if boot_l < 300:
        return "Pequena"
    elif boot_l <= 450:
        return "Média"
    else:
        return "Grande"


def categorize_frunk(frunk_l: int | None) -> str:
    """Categorize frunk volume."""
    if frunk_l is None:
        return "Sem frunk"
    elif frunk_l == 0:
        return "Sem frunk (0 L)"
    elif frunk_l <= 30:
        return "Frunk pequeno"
    else:
        return "Frunk grande"


class TestDimensionsBoundaryAndCategoryPartition(unittest.TestCase):
    """Boundary Value Analysis & Category Partitioning for Vehicle Dimensions (mm)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self.web = raiz / "web"
        (self.web / "img").mkdir(parents=True)
        # Create minimal valid PNG image
        header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x04\xb0\x00\x00\x03\x20\x08\x02\x00\x00\x00"
        (self.web / "img" / "foto.png").write_bytes(header + b"\x00" * 20000)
        patch = mock.patch.object(validate_data, "ROOT", raiz)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_length_category_partitions(self):
        """Verify length categorization across partition boundaries."""
        self.assertEqual(categorize_length(3500), "Micro / Citadino")
        self.assertEqual(categorize_length(3799), "Micro / Citadino")
        self.assertEqual(categorize_length(3800), "Compacto")
        self.assertEqual(categorize_length(4200), "Compacto")
        self.assertEqual(categorize_length(4400), "Compacto")
        self.assertEqual(categorize_length(4401), "Familiar / Grande")
        self.assertEqual(categorize_length(5000), "Familiar / Grande")

    def test_width_category_partitions(self):
        """Verify width categorization across partition boundaries."""
        self.assertEqual(categorize_width(1600), "Estreito")
        self.assertEqual(categorize_width(1749), "Estreito")
        self.assertEqual(categorize_width(1750), "Médio")
        self.assertEqual(categorize_width(1800), "Médio")
        self.assertEqual(categorize_width(1850), "Médio")
        self.assertEqual(categorize_width(1851), "Largo")
        self.assertEqual(categorize_width(2000), "Largo")

    def test_height_category_partitions(self):
        """Verify height categorization across partition boundaries."""
        self.assertEqual(categorize_height(1450), "Baixo")
        self.assertEqual(categorize_height(1499), "Baixo")
        self.assertEqual(categorize_height(1500), "Médio")
        self.assertEqual(categorize_height(1600), "Médio")
        self.assertEqual(categorize_height(1650), "Médio")
        self.assertEqual(categorize_height(1651), "Alto")
        self.assertEqual(categorize_height(1800), "Alto")

    def test_length_boundary_validation_in_schema(self):
        """Validator rejects length_mm <= 0 and accepts length_mm >= 1."""
        for invalid_val in [0, -1, -3800]:
            with self.subTest(length=invalid_val):
                cat = build_test_catalog(dimensions={"length_mm": invalid_val, "width_mm": 1780, "height_mm": 1540})
                errors = validate_catalog(cat)
                self.assertTrue(any("dimensions.length_mm" in e for e in errors), f"Failed to reject length={invalid_val}")

        for valid_val in [1, 3799, 3800, 4400, 4401, 5000]:
            with self.subTest(length=valid_val):
                cat = build_test_catalog(dimensions={"length_mm": valid_val, "width_mm": 1780, "height_mm": 1540})
                errors = validate_catalog(cat)
                self.assertEqual(errors, [], f"Unexpected errors for length={valid_val}: {errors}")

    def test_width_boundary_validation_in_schema(self):
        """Validator rejects width_mm <= 0 and accepts width_mm >= 1."""
        for invalid_val in [0, -1, -1750]:
            with self.subTest(width=invalid_val):
                cat = build_test_catalog(dimensions={"length_mm": 4200, "width_mm": invalid_val, "height_mm": 1540})
                errors = validate_catalog(cat)
                self.assertTrue(any("dimensions.width_mm" in e for e in errors), f"Failed to reject width={invalid_val}")

        for valid_val in [1, 1749, 1750, 1850, 1851, 2100]:
            with self.subTest(width=valid_val):
                cat = build_test_catalog(dimensions={"length_mm": 4200, "width_mm": valid_val, "height_mm": 1540})
                errors = validate_catalog(cat)
                self.assertEqual(errors, [], f"Unexpected errors for width={valid_val}: {errors}")

    def test_height_boundary_validation_in_schema(self):
        """Validator rejects height_mm <= 0 and accepts height_mm >= 1."""
        for invalid_val in [0, -1, -1500]:
            with self.subTest(height=invalid_val):
                cat = build_test_catalog(dimensions={"length_mm": 4200, "width_mm": 1780, "height_mm": invalid_val})
                errors = validate_catalog(cat)
                self.assertTrue(any("dimensions.height_mm" in e for e in errors), f"Failed to reject height={invalid_val}")

        for valid_val in [1, 1499, 1500, 1650, 1651, 2000]:
            with self.subTest(height=valid_val):
                cat = build_test_catalog(dimensions={"length_mm": 4200, "width_mm": 1780, "height_mm": valid_val})
                errors = validate_catalog(cat)
                self.assertEqual(errors, [], f"Unexpected errors for height={valid_val}: {errors}")


class TestLuggageBoundaryAndCategoryPartition(unittest.TestCase):
    """Boundary Value Analysis & Category Partitioning for Luggage Volume (L)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        raiz = Path(self._tmp.name)
        self.web = raiz / "web"
        (self.web / "img").mkdir(parents=True)
        header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x04\xb0\x00\x00\x03\x20\x08\x02\x00\x00\x00"
        (self.web / "img" / "foto.png").write_bytes(header + b"\x00" * 20000)
        patch = mock.patch.object(validate_data, "ROOT", raiz)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_boot_category_partitions(self):
        """Verify boot volume categorization across partition boundaries."""
        self.assertEqual(categorize_boot(200), "Pequena")
        self.assertEqual(categorize_boot(299), "Pequena")
        self.assertEqual(categorize_boot(300), "Média")
        self.assertEqual(categorize_boot(400), "Média")
        self.assertEqual(categorize_boot(450), "Média")
        self.assertEqual(categorize_boot(451), "Grande")
        self.assertEqual(categorize_boot(600), "Grande")

    def test_frunk_category_partitions(self):
        """Verify frunk volume categorization across partition boundaries."""
        self.assertEqual(categorize_frunk(None), "Sem frunk")
        self.assertEqual(categorize_frunk(0), "Sem frunk (0 L)")
        self.assertEqual(categorize_frunk(15), "Frunk pequeno")
        self.assertEqual(categorize_frunk(30), "Frunk pequeno")
        self.assertEqual(categorize_frunk(31), "Frunk grande")
        self.assertEqual(categorize_frunk(80), "Frunk grande")

    def test_boot_boundary_validation_in_schema(self):
        """Validator rejects boot_capacity_l <= 0 and accepts boot_capacity_l >= 1."""
        for invalid_val in [0, -1, -300]:
            with self.subTest(boot=invalid_val):
                cat = build_test_catalog(luggage_capacity={"boot_capacity_l": invalid_val, "frunk_capacity_l": None})
                errors = validate_catalog(cat)
                self.assertTrue(any("luggage_capacity.boot_capacity_l" in e for e in errors), f"Failed to reject boot={invalid_val}")

        for valid_val in [1, 299, 300, 450, 451, 800]:
            with self.subTest(boot=valid_val):
                cat = build_test_catalog(luggage_capacity={"boot_capacity_l": valid_val, "frunk_capacity_l": None})
                errors = validate_catalog(cat)
                self.assertEqual(errors, [], f"Unexpected errors for boot={valid_val}: {errors}")

    def test_frunk_boundary_validation_in_schema(self):
        """Validator rejects frunk_capacity_l < 0 (non-null) and accepts frunk_capacity_l >= 0 or None."""
        for invalid_val in [-1, -50]:
            with self.subTest(frunk=invalid_val):
                cat = build_test_catalog(luggage_capacity={"boot_capacity_l": 350, "frunk_capacity_l": invalid_val})
                errors = validate_catalog(cat)
                self.assertTrue(any("luggage_capacity.frunk_capacity_l" in e for e in errors), f"Failed to reject frunk={invalid_val}")

        for valid_val in [None, 0, 1, 30, 31, 100]:
            with self.subTest(frunk=valid_val):
                cat = build_test_catalog(luggage_capacity={"boot_capacity_l": 350, "frunk_capacity_l": valid_val})
                errors = validate_catalog(cat)
                self.assertEqual(errors, [], f"Unexpected errors for frunk={valid_val}: {errors}")


if __name__ == "__main__":
    unittest.main()

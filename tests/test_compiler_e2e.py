"""Integration & E2E Test Suite for Data Compiler and Cache Buster.

Requirements tested:
- R2. Schema Expansion & Data Enrichment compiler output
- R3. UI & Test Suite Integrity compiler cache-busting (?v=<hash> in index.html)

Derivation of Expected Output:
- Interface Contract in PROJECT.md: `compile_data.py` MUST serialize all model fields
  to `web/assets/js/car_data.js` under global variable `CAR_DATA`.
- `compile_data.stamp_index(bundle)` MUST update `?v=<12-char sha256 hash>` in `web/index.html`.
"""

import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import compile_data


class TestCompilerPipeline(unittest.TestCase):
    """Test suite for compile_data.py compilation pipeline."""

    def test_actual_catalog_compilation_contains_new_fields(self):
        """Verify real catalog compilation includes dimensions, luggage, pros, and cons."""
        catalog = compile_data.load_catalog()
        models = catalog.get("models", [])
        self.assertTrue(len(models) > 0, "Catalog contains no models")

        # Compile catalog to output bundle string
        dealers = {dealer["brand"]: dealer for dealer in compile_data.load_dealers()["dealers"]}
        expected_output = "// Gerado automaticamente por scripts/compile_data.py; não editar.\n"
        expected_output += "const CAR_DATA = " + json.dumps(models, indent=2, ensure_ascii=False) + ";\n"
        expected_output += "const DEALER_DATA = " + json.dumps(dealers, indent=2, ensure_ascii=False) + ";\n"

        # Check compiled bundle file
        bundle_path = ROOT / "web" / "assets" / "js" / "car_data.js"
        self.assertTrue(bundle_path.exists(), "car_data.js does not exist")
        bundle_content = bundle_path.read_text(encoding="utf-8")

        self.assertEqual(bundle_content, expected_output, "Compiled car_data.js differs from expected serialized JSON")

        # Parse CAR_DATA from compiled bundle content
        match = re.search(r"const CAR_DATA = (\[.*?\]);\nconst DEALER_DATA =", bundle_content, re.DOTALL)
        self.assertIsNotNone(match, "Failed to parse CAR_DATA from bundle")
        compiled_models = json.loads(match.group(1))

        for model in compiled_models:
            label = f"{model.get('brand')} {model.get('model')}"
            self.assertIn("dimensions", model, f"{label} missing 'dimensions' field in compiled bundle")
            self.assertIn("luggage_capacity", model, f"{label} missing 'luggage_capacity' field in compiled bundle")
            self.assertIn("pros", model, f"{label} missing 'pros' field in compiled bundle")
            self.assertIn("cons", model, f"{label} missing 'cons' field in compiled bundle")

            dims = model["dimensions"]
            self.assertIsInstance(dims.get("length_mm"), int, f"{label} length_mm invalid")
            self.assertIsInstance(dims.get("width_mm"), int, f"{label} width_mm invalid")
            self.assertIsInstance(dims.get("height_mm"), int, f"{label} height_mm invalid")

            luggage = model["luggage_capacity"]
            self.assertIsInstance(luggage.get("boot_capacity_l"), int, f"{label} boot_capacity_l invalid")

            self.assertIsInstance(model["pros"], list, f"{label} pros must be a list")
            self.assertIsInstance(model["cons"], list, f"{label} cons must be a list")

    def test_cache_buster_hash_computation_and_stamping(self):
        """Test index.html cache buster stamping with SHA256 prefix."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            index_path = tmp_path / "index.html"
            initial_html = (
                '<!DOCTYPE html>\n<html>\n<head>\n'
                '<script src="assets/js/car_data.js"></script>\n'
                '</head>\n<body></body>\n</html>'
            )
            index_path.write_text(initial_html, encoding="utf-8")

            test_bundle = "const CAR_DATA = [{'brand': 'Test', 'model': 'EV'}];"
            expected_hash = hashlib.sha256(test_bundle.encode("utf-8")).hexdigest()[:12]

            with mock.patch.object(compile_data, "INDEX_PATH", index_path):
                updated = compile_data.stamp_index(test_bundle)
                self.assertTrue(updated, "stamp_index returned False on initial stamping")

                content_after = index_path.read_text(encoding="utf-8")
                expected_script_tag = f'<script src="assets/js/car_data.js?v={expected_hash}"></script>'
                self.assertIn(expected_script_tag, content_after)

                # Re-stamping identical bundle should return False (idempotent)
                self.assertFalse(compile_data.stamp_index(test_bundle))
                self.assertEqual(index_path.read_text(encoding="utf-8"), content_after)

                # Stamping updated bundle should yield new hash
                modified_bundle = "const CAR_DATA = [{'brand': 'Test', 'model': 'EV2'}];"
                new_expected_hash = hashlib.sha256(modified_bundle.encode("utf-8")).hexdigest()[:12]
                self.assertNotEqual(expected_hash, new_expected_hash)

                self.assertTrue(compile_data.stamp_index(modified_bundle))
                content_modified = index_path.read_text(encoding="utf-8")
                new_script_tag = f'<script src="assets/js/car_data.js?v={new_expected_hash}"></script>'
                self.assertIn(new_script_tag, content_modified)

    def test_index_html_currently_stamped_with_valid_hash(self):
        """Verify actual web/index.html has a valid cache-buster hash matching car_data.js."""
        index_file = ROOT / "web" / "index.html"
        bundle_file = ROOT / "web" / "assets" / "js" / "car_data.js"

        self.assertTrue(index_file.exists(), "web/index.html missing")
        self.assertTrue(bundle_file.exists(), "web/assets/js/car_data.js missing")

        html_text = index_file.read_text(encoding="utf-8")
        bundle_text = bundle_file.read_text(encoding="utf-8")

        expected_hash = hashlib.sha256(bundle_text.encode("utf-8")).hexdigest()[:12]
        match = re.search(r'<script src="assets/js/car_data\.js\?v=([0-9a-f]{12})"', html_text)

        self.assertIsNotNone(match, "index.html does not contain valid ?v=<12-hex-hash> attribute")
        actual_hash = match.group(1)
        self.assertEqual(actual_hash, expected_hash, f"Cache hash mismatch in index.html: got {actual_hash}, expected {expected_hash}")


if __name__ == "__main__":
    unittest.main()

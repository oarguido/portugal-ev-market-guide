import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import compile_data
import serve
from archive_unused_images import unused_images
from validate_data import effective_price, validate_catalog, validate_dealers


class ProjectDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = compile_data.load_catalog()
        cls.models = cls.catalog["models"]
        cls.dealers = compile_data.load_dealers()

    def test_catalog_is_valid(self):
        self.assertEqual(validate_catalog(self.catalog), [])

    def test_market_pool_is_substantially_expanded(self):
        self.assertGreaterEqual(len(self.models), 30)
        self.assertGreaterEqual(sum(len(model["variants"]) for model in self.models), 40)

    def test_discovery_sources_are_secondary_only(self):
        self.assertTrue(self.catalog["discovery_sources"])
        for source in self.catalog["discovery_sources"]:
            self.assertEqual(source["type"], "secondary_market_discovery")
            self.assertTrue(source["usage_policy"])
            self.assertTrue(source["known_limitations"])

    def test_every_entry_is_a_current_pt_bev_under_40000(self):
        self.assertEqual(self.catalog["scope"]["vehicle_type"], "M1 passenger car")
        self.assertEqual(self.catalog["scope"]["condition"], "new")
        for model in self.models:
            self.assertEqual(model["powertrain"], "BEV")
            self.assertEqual(model["availability_status"], "available")
            for variant in model["variants"]:
                self.assertLessEqual(effective_price(variant["pricing"]), 40_000)
                if variant["pricing"].get("particular_campaign_price_vat_incl"):
                    self.assertTrue(variant["pricing"].get("campaign_conditions"))

    def test_every_vehicle_source_is_official(self):
        for model in self.models:
            for source in model["data_sources"]:
                self.assertTrue(
                    source["type"].startswith("official_"),
                    f"{model['brand']} {model['model']}: {source['type']}",
                )

    def test_every_model_has_a_real_local_photo(self):
        for model in self.models:
            image = ROOT / "web" / model["image_path"]
            self.assertTrue(image.is_file(), f"Missing {model['brand']} {model['model']}")
            self.assertGreater(image.stat().st_size, 5_000)

    def test_vehicle_image_directory_has_no_unreferenced_files(self):
        self.assertEqual(unused_images(), [])

    def test_every_brand_has_one_nearby_official_dealer(self):
        self.assertEqual(validate_dealers(self.catalog, self.dealers), [])
        active_brands = {model["brand"] for model in self.models}
        dealer_brands = [dealer["brand"] for dealer in self.dealers["dealers"]]
        self.assertEqual(set(dealer_brands), active_brands)
        self.assertEqual(len(dealer_brands), len(active_brands))

    def test_generated_bundle_matches_catalog(self):
        compile_data.compile_data()
        text = compile_data.BUNDLE_PATH.read_text(encoding="utf-8")
        payload = text.split("const CAR_DATA = ", 1)[1].split(";\nconst DEALER_DATA = ", 1)[0]
        self.assertEqual(json.loads(payload), self.models)

    def test_web_entrypoint_references_existing_local_assets(self):
        """Todo o asset local referenciado pelo index.html tem de existir.

        Derivado do HTML em vez de uma lista fixa: uma lista fixa esquece um
        ficheiro novo (specs.js esteve carregado sem estar coberto) e continua
        verde.
        """
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        references = re.findall(r'(?:src|href)="([^"]+)"', html)
        local = [
            reference
            for reference in references
            if not reference.startswith(("http://", "https://", "//", "#", "mailto:", "tel:", "data:"))
        ]
        self.assertTrue(local, "o index.html tem de referenciar assets locais")
        for reference in local:
            with self.subTest(asset=reference):
                self.assertTrue((ROOT / "web" / reference).is_file(), f"asset ausente: {reference}")

    def test_web_entrypoint_loads_every_application_module(self):
        """A aplicação não carrega o bundle sem os módulos que o interpretam."""
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        modules = {path.name for path in (ROOT / "web" / "assets" / "js").glob("*.js")}
        loaded = set(re.findall(r'<script src="assets/js/([^"]+)"', html))
        self.assertEqual(modules, loaded, "módulo em assets/js/ não carregado pelo index.html")

    def test_offline_page_has_no_remote_resources(self):
        """A aplicação é offline: nenhum src/href pode apontar para a rede."""
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        remote = re.findall(r'(?:src|href)="((?:https?:)?//[^"]+)"', html)
        self.assertEqual(remote, [], f"recursos remotos no index.html: {remote}")

    def test_server_uses_next_port_when_preferred_port_is_occupied(self):
        replacement = mock.Mock()
        replacement.server_address = (serve.HOST, 8001)
        address_in_use = OSError(48, "Address already in use")

        with mock.patch.object(
            serve,
            "ProjectHTTPServer",
            side_effect=(address_in_use, replacement),
        ) as server_class:
            server, selected_port = serve.create_server(8000, attempts=10)

        self.assertIs(server, replacement)
        self.assertEqual(selected_port, 8001)
        self.assertEqual(
            [call.args[0] for call in server_class.call_args_list],
            [(serve.HOST, 8000), (serve.HOST, 8001)],
        )


if __name__ == "__main__":
    unittest.main()

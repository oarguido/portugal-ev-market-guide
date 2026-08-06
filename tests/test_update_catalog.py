import contextlib
import copy
import io
import pathlib
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import update_catalog
from update_catalog import (
    BINARY_FINGERPRINT_VERSION,
    FETCH_ATTEMPTS,
    HTML_FINGERPRINT_VERSION,
    accept_photo_proposals,
    blocked_snapshot,
    build_snapshot,
    fetch,
    normalized_visible_text,
    refresh_photo,
    snapshot_changed,
)


class SourceFingerprintTests(unittest.TestCase):
    def test_dynamic_scripts_styles_and_attributes_do_not_change_html_fingerprint(self):
        first = b"""
            <html data-request="abc"><head>
              <meta name="description" content="BYD Dolphin desde 33 000 euros">
              <style>.nonce-1 { color: red }</style>
              <script>window.requestId = "123";</script>
            </head><body><h1>BYD Dolphin</h1><p>Autonomia WLTP 427 km</p></body></html>
        """
        second = b"""
            <html data-request="xyz"><head>
              <meta content="BYD Dolphin desde 33 000 euros" name="description">
              <style>.nonce-9 { color: blue }</style>
              <script>window.requestId = "999";</script>
            </head><body>
              <h1>BYD Dolphin</h1> <p>Autonomia WLTP 427 km</p>
            </body></html>
        """
        first_snapshot = build_snapshot(first, "https://example.pt/dolphin")
        second_snapshot = build_snapshot(second, "https://example.pt/dolphin")
        self.assertEqual(first_snapshot["fingerprint_version"], HTML_FINGERPRINT_VERSION)
        self.assertEqual(first_snapshot["sha256"], second_snapshot["sha256"])
        self.assertNotEqual(first_snapshot["raw_sha256"], second_snapshot["raw_sha256"])

    def test_visible_price_change_changes_html_fingerprint(self):
        old = build_snapshot(
            b"<html><body><p>Preco com IVA: 33 000 euros</p></body></html>",
            "https://example.pt/modelo",
        )
        new = build_snapshot(
            b"<html><body><p>Preco com IVA: 34 000 euros</p></body></html>",
            "https://example.pt/modelo",
        )
        self.assertTrue(snapshot_changed(old, new))

    def test_pdf_uses_raw_binary_fingerprint(self):
        snapshot = build_snapshot(b"%PDF-1.7 example", "https://example.pt/precos.pdf")
        self.assertEqual(snapshot["fingerprint_version"], BINARY_FINGERPRINT_VERSION)
        self.assertEqual(snapshot["sha256"], snapshot["raw_sha256"])

    def test_legacy_hash_is_compared_with_current_raw_hash_during_migration(self):
        body = b"<html><body>Modelo sem alteracoes</body></html>"
        current = build_snapshot(body, "https://example.pt/modelo")
        self.assertFalse(snapshot_changed({"sha256": current["raw_sha256"]}, current))
        self.assertTrue(snapshot_changed({"sha256": "outro-hash"}, current))

    def test_http_status_transitions_are_changes(self):
        blocked = blocked_snapshot(403, "https://example.pt/modelo")
        self.assertFalse(snapshot_changed({"http_status": 403}, blocked))
        self.assertFalse(snapshot_changed({"http_status": 429}, blocked))
        self.assertTrue(
            snapshot_changed(
                {"http_status": 403},
                build_snapshot(b"<html><body>Disponivel</body></html>", "https://example.pt/modelo"),
            )
        )

    def test_dealer_open_closed_status_is_ignored(self):
        opened = normalized_visible_text(
            b"<html><body><h1>Stand Porto</h1><p>Atualmente aberto</p></body></html>"
        )
        closed = normalized_visible_text(
            b"<html><body><h1>Stand Porto</h1><p>Atualmente fechado</p></body></html>"
        )
        self.assertEqual(opened, closed)

    @patch("update_catalog.time.sleep")
    @patch("update_catalog.urllib.request.urlopen")
    def test_fetch_retries_transient_http_errors(self, urlopen, _sleep):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"<html>OK</html>"
        response.__enter__.return_value.geturl.return_value = "https://example.pt/modelo"
        urlopen.side_effect = [
            urllib.error.HTTPError(
                "https://example.pt/modelo", 503, "Unavailable", {}, None
            ),
            response,
        ]
        body, destination = fetch("https://example.pt/modelo")
        self.assertEqual(body, b"<html>OK</html>")
        self.assertEqual(destination, "https://example.pt/modelo")
        self.assertEqual(urlopen.call_count, 2)

    @patch("update_catalog.time.sleep")
    @patch("update_catalog.urllib.request.urlopen")
    def test_fetch_still_fails_after_retry_limit(self, urlopen, _sleep):
        urlopen.side_effect = urllib.error.HTTPError(
            "https://example.pt/modelo", 503, "Unavailable", {}, None
        )
        with self.assertRaises(urllib.error.HTTPError):
            fetch("https://example.pt/modelo")
        # Ligado à constante: as tentativas baixaram de 3 para 2 quando o browser
        # passou a ser a alternativa, e um número fixo aqui só repetia o valor.
        self.assertEqual(urlopen.call_count, FETCH_ATTEMPTS)


    @patch("update_catalog.subprocess.run")
    @patch("update_catalog.time.sleep")
    @patch("update_catalog.urllib.request.urlopen")
    def test_blocked_sources_are_listed_for_manual_review(self, urlopen, _sleep, _run):
        """Um 403 nao prova que a pagina nao mudou: tem de aparecer no relatorio."""
        urlopen.side_effect = urllib.error.HTTPError(
            "https://bloqueado.pt/modelo", 403, "Forbidden", {}, None
        )
        catalog = {
            "discovery_sources": [],
            "models": [
                {
                    "brand": "Marca",
                    "model": "Modelo",
                    "official_link": "https://bloqueado.pt/modelo",
                    "data_sources": [{"url": "https://bloqueado.pt/modelo"}],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            cache = pathlib.Path(tmp) / "source_snapshots.json"
            output = io.StringIO()
            with (
                patch("update_catalog.load_catalog", return_value=catalog),
                patch("update_catalog.load_dealers", return_value={"dealers": []}),
                patch("update_catalog.CACHE", cache),
                patch("sys.argv", ["update_catalog.py"]),
                contextlib.redirect_stdout(output),
            ):
                code = update_catalog.main()
        printed = output.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("REVER MANUALMENTE NO BROWSER", printed)
        self.assertIn("https://bloqueado.pt/modelo (HTTP 403)", printed)


class PhotoProposalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.root_patch = patch.object(update_catalog, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.tmp.cleanup)
        self.model = {
            "brand": "Marca",
            "model": "Modelo",
            "official_link": "https://marca.pt/modelo",
            "image_path": "assets/images/vehicles/marca-modelo/official.jpg",
            "last_verified": "2026-01-01",
            "data_sources": [{"url": "https://marca.pt/modelo", "verified_on": "2026-01-01"}],
        }
        self.canonical = self.root / "web" / self.model["image_path"]
        self.canonical.parent.mkdir(parents=True)
        self.original = b"canonical local photo"
        self.canonical.write_bytes(self.original)
        self.candidate = b"\xff\xd8" + b"photo from a different model" * 300

    def test_mismatched_og_image_stays_proposal_and_cannot_replace_canonical(self):
        html = b'<meta property="og:image" content="/other-model.jpg">'
        with patch("update_catalog.fetch", return_value=(self.candidate, "https://marca.pt/other-model.jpg")):
            self.assertTrue(refresh_photo(self.model, html, "https://marca.pt/modelo"))

        self.assertEqual(self.model["image_path"], "assets/images/vehicles/marca-modelo/official.jpg")
        self.assertEqual(self.canonical.read_bytes(), self.original)
        proposal = self.root / "archive" / "photo-proposals" / "marca-modelo" / "official.jpg"
        self.assertEqual(proposal.read_bytes(), self.candidate)
        manifest = (proposal.parent.parent / "manifest.json").read_text(encoding="utf-8")
        self.assertIn("other-model.jpg", manifest)

    def test_missing_og_image_does_not_create_or_replace_photo(self):
        with patch("update_catalog.fetch") as fetch_mock:
            self.assertFalse(refresh_photo(self.model, b"<html><body>sem imagem</body></html>", "https://marca.pt/modelo"))
        fetch_mock.assert_not_called()
        self.assertEqual(self.model["image_path"], "assets/images/vehicles/marca-modelo/official.jpg")
        self.assertEqual(self.canonical.read_bytes(), self.original)
        self.assertFalse((self.root / "archive" / "photo-proposals").exists())

    def test_acceptance_is_explicit_and_does_not_refresh_verification_metadata(self):
        html = b'<meta property="og:image" content="/model.jpg">'
        with patch("update_catalog.fetch", return_value=(self.candidate, "https://marca.pt/model.jpg")):
            refresh_photo(self.model, html, "https://marca.pt/modelo")

        catalog = {"models": [copy.deepcopy(self.model)]}
        accepted = accept_photo_proposals(catalog)
        self.assertEqual(accepted, ["Marca Modelo"])
        accepted_model = catalog["models"][0]
        self.assertEqual(self.canonical.read_bytes(), self.candidate)
        self.assertEqual(accepted_model["last_verified"], "2026-01-01")
        self.assertEqual(accepted_model["data_sources"][0]["verified_on"], "2026-01-01")

    @patch("update_catalog.subprocess.run")
    def test_refresh_photos_flag_preserves_catalog_and_dates(self, run):
        catalog = {"discovery_sources": [], "models": [copy.deepcopy(self.model)]}
        page = b'<html><meta property="og:image" content="/model.jpg"></html>'
        cache = self.root / "source_snapshots.json"
        with (
            patch.object(update_catalog, "CACHE", cache),
            patch.object(update_catalog, "load_catalog", return_value=catalog),
            patch.object(update_catalog, "load_dealers", return_value={"dealers": []}),
            patch("update_catalog.fetch", side_effect=[(page, "https://marca.pt/modelo"), (self.candidate, "https://marca.pt/model.jpg")]),
            patch("sys.argv", ["update_catalog.py", "--refresh-photos"]),
        ):
            code = update_catalog.main()

        self.assertEqual(code, 0)
        self.assertEqual(catalog["models"][0], self.model)
        self.assertEqual(run.call_count, 4)
        self.assertTrue((self.root / "archive" / "photo-proposals" / "marca-modelo" / "official.jpg").exists())


if __name__ == "__main__":
    unittest.main()

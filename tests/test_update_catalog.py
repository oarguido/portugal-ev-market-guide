import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from update_catalog import (
    BINARY_FINGERPRINT_VERSION,
    HTML_FINGERPRINT_VERSION,
    blocked_snapshot,
    build_snapshot,
    fetch,
    normalized_visible_text,
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
        self.assertEqual(urlopen.call_count, 3)


if __name__ == "__main__":
    unittest.main()

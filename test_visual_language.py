import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zincintel.dashboard_v27 import build_dashboard_v27
from zincintel.research_pages import build_research_pages
from zincintel.visual_language import (ASSETS, SERIES_STYLES, asset_icon,
                                       source_badge, source_identity)


class VisualLanguageTest(unittest.TestCase):
    def test_series_have_one_semantic_style(self):
        required = {"close", "sma14", "sma30", "ema20", "rsi14", "up", "down"}
        self.assertTrue(required.issubset(SERIES_STYLES))
        for key in required:
            self.assertRegex(SERIES_STYLES[key]["color"], r"^#[0-9A-Fa-f]{6}$")
            self.assertGreater(SERIES_STYLES[key]["width"], 0)
        self.assertNotEqual(SERIES_STYLES["close"]["color"], SERIES_STYLES["ema20"]["color"])
        self.assertNotEqual(SERIES_STYLES["sma14"]["dash"], SERIES_STYLES["sma30"]["dash"])

    def test_every_public_market_has_an_accessible_icon(self):
        expected = {"lme_zinc", "shfe_zinc", "gold", "usdjpy", "dxy", "us_treasury"}
        self.assertTrue(expected.issubset(ASSETS))
        for key in expected:
            icon = asset_icon(key)
            self.assertIn(f"data-asset-icon='{key}'", icon)
            self.assertIn("role='img'", icon)
            self.assertIn("aria-label=", icon)

    def test_source_identity_never_upgrades_provenance(self):
        cases = [
            (("A_OFFICIAL_EXCHANGE", "AVAILABLE"), ("official", "OFFICIAL")),
            (("B_PUBLIC_API", "AVAILABLE"), ("api", "PUBLIC API")),
            (("B_PUBLIC_REFERENCE", "AVAILABLE"), ("reference", "PUBLIC REFERENCE")),
            (("B_PUBLIC_REFERENCE", "CURRENT_OR_MISSING"), ("reference", "PUBLIC REFERENCE")),
            (("B_MARKET_SOURCE_RESTRICTED", "AVAILABLE"), ("market", "MARKET SOURCE")),
            (("DERIVED_FROM_OFFICIAL", "AVAILABLE"), ("derived", "DERIVED")),
            (("B_PUBLIC_REFERENCE", "CARRY_FORWARD_LAST_VERIFIED"), ("carry", "CARRY FORWARD")),
            ((None, "MISSING"), ("missing", "MISSING")),
        ]
        for inputs, expected in cases:
            identity = source_identity(*inputs)
            self.assertEqual((identity["key"], identity["label"]), expected)
        badge = source_badge("B_PUBLIC_REFERENCE", "AVAILABLE")
        self.assertIn("data-source-grade='B_PUBLIC_REFERENCE'", badge)
        self.assertIn("PUBLIC REFERENCE", badge)
        self.assertNotIn(">OFFICIAL<", badge)

    def test_generated_pages_share_icons_legends_and_identity_badges(self):
        primary_markets = {"lme_zinc", "shfe_zinc", "gold", "usdjpy", "dxy", "us_treasury"}
        snapshot = json.loads(Path("data/latest_snapshot.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as folder, \
                patch("zincintel.dashboard_v27.PUBLIC_DIR", Path(folder)), \
                patch("zincintel.research_pages.PUBLIC_DIR", Path(folder)), \
                patch("zincintel.dashboard_v27.build_legacy_dashboard"):
            build_dashboard_v27(snapshot, {}, [], {})
            build_research_pages(snapshot)
            index = (Path(folder) / "index.html").read_text(encoding="utf-8")
            markets = (Path(folder) / "markets.html").read_text(encoding="utf-8")
            radar = (Path(folder) / "radar.html").read_text(encoding="utf-8")
            journal = (Path(folder) / "journal.html").read_text(encoding="utf-8")
            status = (Path(folder) / "system-status.html").read_text(encoding="utf-8")
        for page in (index, markets, radar, journal, status):
            self.assertIn("--series-close:#59d7ff", page)
            self.assertIn("DATA IDENTITY", page)
            self.assertIn("PUBLIC REFERENCE", page)
            self.assertIn("CARRY FORWARD", page)
            self.assertIn("MISSING", page)
        for key in primary_markets:
            self.assertIn(f"data-asset-icon='{key}'", index if key == "us_treasury" else markets)
        self.assertIn("aria-label='Chart series legend'", markets)
        self.assertIn("stroke-dasharray:8 5", markets)
        self.assertIn("stroke-dasharray:12 6", markets)
        self.assertIn("data-source-kind=", index)


if __name__ == "__main__":
    unittest.main()

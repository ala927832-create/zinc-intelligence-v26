"""Durable baseline guardrails established before the visual redesign phases.

These checks deliberately avoid freezing market prices or presentation details.
They protect the data identity, public/private boundary, navigation boundary and
weekday schedule while later phases are free to redesign the UI.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class Phase0GuardrailsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = json.loads(
            (ROOT / "data" / "latest_snapshot.json").read_text(encoding="utf-8")
        )

    def test_visible_navigation_has_four_research_pages_only(self) -> None:
        visible_pages = ("index.html", "markets.html", "radar.html", "journal.html")
        for name in visible_pages:
            page = (ROOT / "public" / name).read_text(encoding="utf-8")
            for required in visible_pages:
                self.assertIn(required, page, f"{name} is missing {required} navigation")
            self.assertNotIn("system-status.html", page)

        status_page = ROOT / "public" / "system-status.html"
        self.assertTrue(status_page.is_file())
        self.assertIn("internal operations view", status_page.read_text(encoding="utf-8"))

    def test_public_pages_share_the_frozen_snapshot_date(self) -> None:
        run_date = self.snapshot.get("run_date")
        self.assertRegex(str(run_date), r"^\d{4}-\d{2}-\d{2}$")
        for name in ("index.html", "markets.html", "radar.html", "journal.html"):
            page = (ROOT / "public" / name).read_text(encoding="utf-8")
            self.assertIn(run_date, page, f"{name} does not show the snapshot run date")

    def test_lme_remains_close_only_and_shfe_retains_its_identity(self) -> None:
        self.assertEqual("CLOSE_ONLY", self.snapshot.get("technical_mode"))
        candle = self.snapshot.get("daily_candle_status", {})
        self.assertEqual("MISSING", candle.get("status"))
        self.assertEqual(0, candle.get("complete_sessions"))

        research = self.snapshot.get("market_research", {})
        close = research.get("close_series", {})
        self.assertEqual("MISSING_UNVERIFIED_SOURCE", close.get("open_status"))
        self.assertEqual("B_PUBLIC_REFERENCE", close.get("source_grade"))
        self.assertNotIn("ohlc", str(close.get("series", "")).lower())

        shfe = research.get("shfe_zinc", {})
        self.assertEqual("SHFE", shfe.get("market"))
        self.assertEqual("A_OFFICIAL_EXCHANGE", shfe.get("source_grade"))
        self.assertIn("SHFE", shfe.get("series", ""))

    def test_available_cross_asset_series_keep_provenance(self) -> None:
        cross_assets = self.snapshot.get("market_research", {}).get("cross_assets", {})
        for key in ("gold", "usdjpy", "dxy"):
            series = cross_assets.get(key, {})
            self.assertEqual("AVAILABLE", series.get("status"), key)
            for field in ("market_identity", "source", "source_grade", "as_of", "series_type"):
                self.assertTrue(series.get(field), f"{key} missing {field}")
            self.assertEqual("UNAVAILABLE", series.get("execution_quote"), key)

    def test_weekday_schedule_and_single_writer_boundary_are_present(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "daily_monitor.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn('cron: "30 2 * * 1-5"', workflow)
        self.assertIn('cron: "30 9 * * 1-5"', workflow)
        self.assertIn("Persist verified state and research journals", workflow)
        self.assertIn('git push origin "HEAD:${GITHUB_REF_NAME}"', workflow)
        self.assertIn("Block private OHLC in public state and Pages", workflow)


if __name__ == "__main__":
    unittest.main()

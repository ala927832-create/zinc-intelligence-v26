import json
import unittest
from pathlib import Path


class N8nTemplateTest(unittest.TestCase):
    def test_templates_are_valid_and_secret_free(self):
        root = Path("automation/n8n")
        for name in ("market_research_agent.json", "official_news_digest.json"):
            text = (root / name).read_text(encoding="utf-8")
            workflow = json.loads(text)
            self.assertFalse(workflow["active"])
            self.assertTrue(workflow["nodes"])
            self.assertNotIn("sk-", text)
            self.assertNotIn("hooks.slack.com/services/", text)
        market = json.loads((root / "market_research_agent.json").read_text())
        names = {node["name"] for node in market["nodes"]}
        self.assertIn("Validate and compact facts", names)
        self.assertIn("LINE daily brief", names)
        self.assertIn("Direction changed?", names)


if __name__ == "__main__":
    unittest.main()

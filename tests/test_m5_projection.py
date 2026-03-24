import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "M5 Portfolio construction" / "script-portfolio-construction.py"


def load_module():
    spec = importlib.util.spec_from_file_location("m5_portfolio", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class PortfolioProjectionTests(unittest.TestCase):
    def test_project_for_portfolio_strips_unused_fields(self):
        module = load_module()
        raw = json.dumps(
            {
                "rotation_score": 4,
                "cycle_phase": "Expansion",
                "stocks": [
                    {
                        "ticker": "ABC",
                        "company_name": "Example Co",
                        "sector": "Tech",
                        "weight": 0.1,
                        "fundamentals": {
                            "market_cap": 100,
                            "pe_forward": 20,
                            "unused_field": "drop-me",
                        },
                        "technicals": {
                            "price_current": 10,
                            "atr_14d": 1.5,
                            "unused_signal": "drop-me",
                        },
                        "derived": {
                            "price_target_upside_pct": 12,
                            "stop_loss_2x_atr": 7,
                            "unused_metric": "drop-me",
                        },
                        "filter_flags": ["ok"],
                        "unused_top_level": "drop-me",
                    }
                ],
            }
        )

        projected = json.loads(module.project_for_portfolio(raw))
        stock = projected["stocks"][0]

        self.assertEqual(projected["rotation_score"], 4)
        self.assertEqual(projected["cycle_phase"], "Expansion")
        self.assertNotIn("unused_top_level", stock)
        self.assertNotIn("unused_field", stock["fundamentals"])
        self.assertNotIn("unused_signal", stock["technicals"])
        self.assertNotIn("unused_metric", stock["derived"])
        self.assertEqual(stock["fundamentals"]["pe_forward"], 20)
        self.assertEqual(stock["derived"]["stop_loss_2x_atr"], 7)


if __name__ == "__main__":
    unittest.main()

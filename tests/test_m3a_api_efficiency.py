import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "M3A Universe generation" / "script-universe-generation-api.py"


def load_module():
    spec = importlib.util.spec_from_file_location("m3a_api", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LoadCacheTests(unittest.TestCase):
    def test_load_cache_keeps_only_fresh_entries_for_positive_ttl(self):
        module = load_module()
        now = module.datetime.now(module.timezone.utc)
        fresh = (now - module.timedelta(days=1)).isoformat()
        stale = (now - module.timedelta(days=10)).isoformat()

        payload = {
            "stocks": [
                {
                    "ticker": "FRESH",
                    "fetched_at": fresh,
                    "fundamentals": {
                        "shares_outstanding": 1,
                        "stock_based_compensation": 1,
                    },
                }
            ],
            "flagged_stocks": [
                {
                    "ticker": "STALE",
                    "fetched_at": stale,
                    "fundamentals": {
                        "shares_outstanding": 1,
                        "stock_based_compensation": 1,
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.json"
            output_path.write_text(json.dumps(payload), encoding="utf-8")

            cache = module.load_cache(output_path, cache_ttl_days=7)

        self.assertEqual(set(cache), {"FRESH"})


class FetchTickerRecordTests(unittest.TestCase):
    def test_fetch_ticker_record_reuses_single_ticker_instance(self):
        module = load_module()
        calls = []

        class FakeTicker:
            pass

        def ticker_factory(symbol):
            calls.append(("factory", symbol))
            return FakeTicker()

        def fake_fetch_technicals(symbol, ticker=None):
            calls.append(("technicals", symbol, ticker))
            return {"avg_volume_30d": 800_000, "price_current": 100.0, "atr_14d": 2.5}

        def fake_fetch_fundamentals(symbol, ticker=None):
            calls.append(("fundamentals", symbol, ticker))
            return {
                "company_name": "Example Co",
                "market_cap": 5_000_000_000,
                "eps_ttm": 2.0,
                "cash_and_equivalents": 10.0,
                "total_debt": 5.0,
                "ebitda_ttm": 1.0,
            }

        def fake_fetch_statements(symbol, ticker=None):
            calls.append(("statements", symbol, ticker))
            return {}

        def fake_fetch_recommendations(symbol, ticker=None):
            calls.append(("recommendations", symbol, ticker))
            return {}

        module.fetch_technicals = fake_fetch_technicals
        module.fetch_fundamentals = fake_fetch_fundamentals
        module.fetch_statements = fake_fetch_statements
        module.fetch_recommendations = fake_fetch_recommendations
        module.validate_filters = lambda fundamentals, technicals: {"passed": True, "flags": []}
        module.compute_derived = lambda fundamentals, technicals: {"stubbed": True}

        record = module.fetch_ticker_record(
            {"ticker": "ABC", "sector": "Tech"},
            ticker_factory=ticker_factory,
        )

        self.assertEqual(record["ticker"], "ABC")
        self.assertEqual(calls[0], ("factory", "ABC"))
        self.assertEqual(len([call for call in calls if call[0] == "factory"]), 1)
        ticker_obj = calls[1][2]
        for kind, _, ticker in calls[1:]:
            self.assertIs(ticker, ticker_obj, kind)


if __name__ == "__main__":
    unittest.main()

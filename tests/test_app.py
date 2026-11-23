"""Tests for the Streamlit converter app (app/). No real API calls are made."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import finance  # noqa: E402
import guard  # noqa: E402
import translator  # noqa: E402

HAS_STREAMLIT = importlib.util.find_spec("streamlit") is not None


def fake_client(code="import pandas as pd\nresult = pd.DataFrame()\n", tokens=1000):
    def send(message):
        meta = SimpleNamespace(prompt_token_count=tokens - 200, candidates_token_count=200,
                               thoughts_token_count=0, cached_content_token_count=0, total_token_count=tokens)
        return SimpleNamespace(text=f"```python\n{code}```", usage_metadata=meta)
    chat = SimpleNamespace(send_message=send)
    return SimpleNamespace(chats=SimpleNamespace(create=lambda **kwargs: chat))


class GuardTests(unittest.TestCase):
    def test_access_code(self):
        self.assertTrue(guard.code_matches(" secret ", "secret"))
        self.assertFalse(guard.code_matches("nope", "secret"))
        self.assertFalse(guard.code_matches("", ""))  # an unset code never unlocks

    def test_upload_limits(self):
        self.assertEqual(guard.check_uploads([("a.sas", b"data x; run;")]), [])
        self.assertTrue(guard.check_uploads([]))
        self.assertTrue(any("only .sas" in p for p in guard.check_uploads([("a.py", b"x")])))
        self.assertTrue(any("limit per file" in p for p in
                            guard.check_uploads([("a.sas", b"x" * (guard.MAX_FILE_BYTES + 1))])))
        many = [(f"{i}.sas", b"x") for i in range(guard.MAX_FILES + 1)]
        self.assertTrue(any("At most" in p for p in guard.check_uploads(many)))

    def test_lockout_after_wrong_codes(self):
        g = guard.SessionGuard()
        for _ in range(guard.MAX_CODE_ATTEMPTS):
            g.record_failed_code(now=1000)
        self.assertGreater(g.locked(now=1001), 0)
        self.assertEqual(g.locked(now=1000 + guard.LOCKOUT_SECONDS + 1), 0)

    def test_rate_limits(self):
        g = guard.SessionGuard()
        for _ in range(guard.RUNS_PER_HOUR):
            g.record_run(now=0)
        self.assertEqual(g.runs_left(now=10), 0)
        self.assertEqual(g.runs_left(now=3601), guard.RUNS_PER_HOUR)
        daily = guard.DailyLimit(limit=2)
        self.assertEqual([daily.take(), daily.take(), daily.take()], [True, True, False])

    def test_decode_falls_back_to_cp1252(self):
        self.assertEqual(guard.decode_sas("café".encode("cp1252")), "café")


class TranslatorAndFinanceTests(unittest.TestCase):
    def test_translates_in_dependency_order_and_checks_syntax(self):
        files = [("2 - stage.sas", "data b; run;"), ("Star_Macros.sas", "%macro m; %mend;"),
                 ("1 - stage.sas", "data a; run;")]
        results = translator.translate_files(files, client=fake_client())
        self.assertEqual([r.sas_name for r in results], ["Star_Macros.sas", "1 - stage.sas", "2 - stage.sas"])
        self.assertTrue(all(r.syntax_ok for r in results))
        self.assertEqual(results[0].python_name, "Star_Macros.py")
        self.assertNotIn("```", results[0].python_code)  # fence stripped
        self.assertEqual(results[0].tokens, 1000)

    def test_syntax_errors_are_flagged_not_executed(self):
        results = translator.translate_files([("a.sas", "data a; run;")], client=fake_client(code="def broken(:\n"))
        self.assertFalse(results[0].syntax_ok)
        self.assertIn("line 1", results[0].syntax_error)

    def test_finance_summary_free_tier_and_priced(self):
        usage = translator.TokenUsageTracker()
        results = translator.translate_files([("a.sas", "data a;\nrun;\n"), ("b.sas", "data b;\nrun;\n")],
                                             client=fake_client(tokens=1_000_000), usage=usage)
        a = finance.default_assumptions()
        free = finance.finance_summary(results, usage, a)
        self.assertEqual(free["totals"]["ai_conversion_cost"], 0)
        self.assertEqual(free["totals"]["tokens_used"], 2_000_000)
        self.assertAlmostEqual(free["totals"]["annual_savings"], a["sas_annual_license_cost"], places=2)
        priced = finance.finance_summary(results, usage, a, input_price=1.0, output_price=2.0)
        # per call: 999,800 prompt x $1/M + 200 output x $2/M = $1.0002
        self.assertAlmostEqual(priced["totals"]["ai_conversion_cost"], 2 * 1.0002, places=4)
        self.assertIn("TOTAL", finance.summary_csv(priced))
        self.assertIn("no review labor", finance.summary_markdown(priced, results))


@unittest.skipUnless(HAS_STREAMLIT, "streamlit not installed (pip install -r app/requirements.txt)")
class AppUiTests(unittest.TestCase):
    def app(self, secrets=True):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(APP_DIR / "streamlit_app.py"), default_timeout=60)
        if secrets:
            at.secrets["GEMINI_API_KEY"] = "test-key"
            at.secrets["ACCESS_CODE"] = "open-sesame"
        return at.run()

    def button(self, at, label):
        return next(b for b in at.button if b.label == label)

    def test_missing_secrets_shows_setup_message(self):
        at = self.app(secrets=False)
        self.assertIn("isn't configured", at.error[0].value)

    def test_access_code_gate(self):
        at = self.app()
        self.assertEqual(len(at.file_uploader if hasattr(at, "file_uploader") else []), 0)
        at.text_input[0].input("wrong")
        self.button(at, "Unlock").click()
        at.run()
        self.assertIn("isn't right", at.error[0].value)
        at.text_input[0].input("open-sesame")
        self.button(at, "Unlock").click()
        at.run()
        self.assertTrue(at.session_state.unlocked)

    def test_example_conversion_end_to_end(self):
        at = self.app()
        at.text_input[0].input("open-sesame")
        self.button(at, "Unlock").click()
        at.run()
        at.toggle[0].set_value(True)
        at.run()
        with mock.patch.object(translator.genai, "Client", return_value=fake_client()):
            self.button(at, "Convert to Python").click()
            at.run()
        self.assertFalse(at.exception)
        results = at.session_state.results
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].sas_name, "Star_Macros.sas")
        labels = [m.label for m in at.metric]
        self.assertIn("Estimated savings / year", labels)
        self.assertIn("Tokens used", labels)
        tokens = next(m for m in at.metric if m.label == "Tokens used")
        self.assertEqual(tokens.value, "4,000")


if __name__ == "__main__":
    unittest.main()

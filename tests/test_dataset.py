import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_pipeline import CallBudget, GeminiKeyPool, build_question_prompt, select_smoke_items
from validate_dataset import validate


class DatasetTests(unittest.TestCase):
    def test_pilot_is_unchanged_prefix(self):
        pilot = json.loads((ROOT / "data/pilot_questions.json").read_text())["items"]
        combined = json.loads((ROOT / "data/all_questions.json").read_text())["items"]
        self.assertEqual(combined[: len(pilot)], pilot)

    def test_external_dataset_quality(self):
        summary = validate(ROOT / "data/expanded_questions.json", require_provenance=True)
        self.assertEqual(summary["items"], 48)

    def test_every_item_works_with_runner_prompt(self):
        for name in ("pilot_questions.json", "expanded_questions.json", "all_questions.json"):
            items = json.loads((ROOT / "data" / name).read_text())["items"]
            for item in items:
                prompt = build_question_prompt(item)
                self.assertIn(f"{item['gold']}) {item['options'][item['gold']]}", prompt)

    def test_smoke_selection_is_small_deterministic_and_balanced(self):
        items = json.loads((ROOT / "data/all_questions.json").read_text())["items"]
        first = select_smoke_items(items, 4)
        second = select_smoke_items(items, 4)
        self.assertEqual([x["id"] for x in first], [x["id"] for x in second])
        self.assertEqual(len(first), 4)
        self.assertEqual({x["gold"] for x in first}, set("ABCD"))
        self.assertGreaterEqual(len({x["domain"] for x in first}), 3)

    def test_call_budget_is_a_hard_limit(self):
        budget = CallBudget(2)
        budget.consume()
        budget.consume()
        with self.assertRaises(RuntimeError):
            budget.consume()

    def test_gemini_key_pool_orders_numbered_keys_and_deduplicates(self):
        pool = GeminiKeyPool({
            "GEMINI_API_KEY3": "third",
            "GEMINI_API_KEY": "first",
            "GEMINI_API_KEY2": "second",
            "GEMINI_API_KEY4": "second",
        })
        self.assertEqual(len(pool), 3)
        self.assertEqual(pool.current_name, "GEMINI_API_KEY")
        self.assertTrue(pool.advance())
        self.assertEqual(pool.current_name, "GEMINI_API_KEY2")
        self.assertTrue(pool.advance())
        self.assertEqual(pool.current_name, "GEMINI_API_KEY3")
        self.assertFalse(pool.advance())


if __name__ == "__main__":
    unittest.main()

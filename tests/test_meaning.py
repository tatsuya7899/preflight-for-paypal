"""Tests for backend/meaning.py — the meaning layer.

Test basis: SPEC-preflight-checker_design.md
  - "意味層の設計" section (2-part split: semantic=LLM, fraud=table-driven;
    undisputed-only mismatch flagging; LLM detection via env; ran=false
    degrade-gracefully behaviour)
  - Acceptance scenarios #2 (semantic mismatch + clause), #7/#8 (fraud
    patterns visible / not-assessable)
  - データモデル・インターフェース section (meaning.* output shape)

LLM network calls are mocked via meaning._get_llm_raw_response — no real API
is ever called by this test file.
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import meaning
from backend import policy


def _order(amount_value="10.00", shipping=None, capture_status="COMPLETED", items=None):
    captures = [{"status": capture_status}] if capture_status else []
    pu = {
        "amount": {"currency_code": "USD", "value": amount_value},
        "items": items or [],
        "payments": {"captures": captures},
    }
    if shipping is not None:
        pu["shipping"] = shipping
    return {"purchase_units": [pu]}


class TestLlmAvailable(unittest.TestCase):
    def test_false_when_no_keys_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("GEMINI_API_KEY", None)
            self.assertFalse(meaning.llm_available())

    def test_true_when_anthropic_key_set(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            self.assertTrue(meaning.llm_available())

    def test_true_when_gemini_key_set(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "g-test"}, clear=True):
            self.assertTrue(meaning.llm_available())


class TestClassifyItemsMismatch(unittest.TestCase):
    """Scenario #2: explicit, undisputed mismatch -> mismatch code set."""

    def test_explicit_digital_declared_as_physical(self):
        raw = json.dumps(
            {
                "category": "DIGITAL",
                "confidence": 0.95,
                "mismatch": "DIGITAL_DECLARED_AS_PHYSICAL",
                "evidence_span": "digital download",
            }
        )
        with mock.patch.object(meaning, "_get_llm_raw_response", return_value=raw):
            items = [
                {
                    "name": "Widget",
                    "category": "PHYSICAL_GOODS",
                    "description": "This is a digital download, delivered by email.",
                }
            ]
            result = meaning.classify_items(items)

        self.assertEqual(result["category"], "DIGITAL")
        self.assertEqual(result["mismatch"], "DIGITAL_DECLARED_AS_PHYSICAL")
        self.assertIn(result["mismatch"], policy.MISMATCH_TO_CHECK)
        self.assertEqual(result["evidence_span"], "digital download")

    def test_ambiguous_item_mismatch_is_null(self):
        raw = json.dumps(
            {
                "category": "PHYSICAL",
                "confidence": 0.4,
                "mismatch": None,
                "evidence_span": "",
            }
        )
        with mock.patch.object(meaning, "_get_llm_raw_response", return_value=raw):
            items = [{"name": "Widget", "category": "PHYSICAL_GOODS", "description": "a widget"}]
            result = meaning.classify_items(items)

        self.assertIsNone(result["mismatch"])
        self.assertEqual(result["category"], "PHYSICAL")

    def test_malformed_llm_response_raises(self):
        with mock.patch.object(meaning, "_get_llm_raw_response", return_value="not json"):
            with self.assertRaises(Exception):
                meaning.classify_items([{"name": "x", "category": "PHYSICAL_GOODS"}])

    def test_unexpected_category_raises(self):
        raw = json.dumps({"category": "NOT_A_REAL_CATEGORY", "confidence": 0.5, "mismatch": None})
        with mock.patch.object(meaning, "_get_llm_raw_response", return_value=raw):
            with self.assertRaises(Exception):
                meaning.classify_items([{"name": "x"}])


class TestRunLlmUnavailable(unittest.TestCase):
    """ran=false when no LLM configured; fraud results still returned (FR-8)."""

    def test_ran_false_and_semantic_none_without_env_keys(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            order = _order(amount_value="10.00", shipping={"address": {}})
            result = meaning.run(order)

        self.assertFalse(result["ran"])
        self.assertIsNone(result["semantic"])
        self.assertIn("fraud_warnings", result)
        self.assertIn("unassessable_patterns", result)
        self.assertIsInstance(result["unassessable_patterns"], list)
        self.assertGreater(len(result["unassessable_patterns"]), 0)


class TestRunLlmRuntimeFailure(unittest.TestCase):
    """ran=false (not an exception) when the LLM call fails at runtime."""

    def test_run_never_raises_on_llm_exception(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            with mock.patch.object(
                meaning, "_get_llm_raw_response", side_effect=TimeoutError("network timeout")
            ):
                order = _order()
                result = meaning.run(order)

        self.assertFalse(result["ran"])
        self.assertIsNone(result["semantic"])
        # fraud layer must still be present and table-driven (independent of LLM failure)
        self.assertIn("fraud_warnings", result)
        self.assertIn("unassessable_patterns", result)


class TestRunLlmAvailableSuccess(unittest.TestCase):
    def test_ran_true_with_semantic_populated(self):
        raw = json.dumps(
            {
                "category": "PHYSICAL",
                "confidence": 0.9,
                "mismatch": None,
                "evidence_span": "",
            }
        )
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            with mock.patch.object(meaning, "_get_llm_raw_response", return_value=raw):
                order = _order(items=[{"name": "Widget", "category": "PHYSICAL_GOODS"}])
                result = meaning.run(order)

        self.assertTrue(result["ran"])
        self.assertEqual(result["semantic"]["category"], "PHYSICAL")


class TestMatchFraudPatternsNoLlm(unittest.TestCase):
    """match_fraud_patterns is table-driven and works with zero LLM env setup."""

    def test_no_shipping_address_flagged_when_capture_completed(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            order = _order(shipping=None, capture_status="COMPLETED")
            result = meaning.match_fraud_patterns(order)

        names = {w["name"] for w in result["fraud_warnings"]}
        self.assertIn("NO_SHIPPING_ADDRESS_ON_FILE", names)

    def test_no_warning_when_shipping_present(self):
        order = _order(shipping={"address": {"country_code": "US"}}, capture_status="COMPLETED")
        result = meaning.match_fraud_patterns(order)

        names = {w["name"] for w in result["fraud_warnings"]}
        self.assertNotIn("NO_SHIPPING_ADDRESS_ON_FILE", names)

    def test_high_value_no_signature_flagged_at_threshold(self):
        order = _order(
            amount_value="800.00",
            shipping={"address": {"country_code": "US"}},
            capture_status="COMPLETED",
        )
        result = meaning.match_fraud_patterns(order)

        names = {w["name"] for w in result["fraud_warnings"]}
        self.assertIn("HIGH_VALUE_NO_SIGNATURE", names)

    def test_below_threshold_not_flagged(self):
        order = _order(
            amount_value="10.00",
            shipping={"address": {"country_code": "US"}},
            capture_status="COMPLETED",
        )
        result = meaning.match_fraud_patterns(order)

        names = {w["name"] for w in result["fraud_warnings"]}
        self.assertNotIn("HIGH_VALUE_NO_SIGNATURE", names)

    def test_unassessable_patterns_always_present_and_separate(self):
        order = _order()
        result = meaning.match_fraud_patterns(order)

        self.assertGreaterEqual(len(result["unassessable_patterns"]), 1)
        warning_names = {w["name"] for w in result["fraud_warnings"]}
        unassessable_names = {p["name"] for p in result["unassessable_patterns"]}
        # Evaluated (matched or not) patterns never appear in unassessable_patterns;
        # the two sets are a strict partition of FRAUD_PATTERNS by api_assessable.
        self.assertEqual(
            unassessable_names,
            {p["name"] for p in policy.unassessable_patterns()},
        )
        self.assertTrue(warning_names.issubset({p["name"] for p in policy.assessable_patterns()}))


if __name__ == "__main__":
    unittest.main()

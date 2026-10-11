"""Tests for backend/rules.py (deterministic rule layer + verdict assembly).

Test basis: SPEC-preflight-checker_design.md
  - "ルール層の条件表(US規約ピン)" section (per-condition pass/fail logic)
  - "データモデル・インターフェース" section (verdict schema: flags/summary/checks/
    meaning/corrections, expected_evidence per check)
  - "意味層の設計" section (semantic mismatch -> check-row mapping, fraud patterns)
  - 受入シナリオ #1 (rule-layer pass/fail), #3 (high-value signature), #6
    (intangible-goods path never fails), #7/#8 (fraud patterns visible/unassessable)
Written from the design spec's tables and fixtures, not from reading rules.py's
implementation.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import policy, rules

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "backend", "fixtures")


def load_order(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


def checks_by_condition(verdict):
    return {c["condition"]: c for c in verdict["checks"]}


class TestOrderA(unittest.TestCase):
    """Order A: physical goods, address present, no high-value amount."""

    def setUp(self):
        self.order = load_order("order_A.json")
        self.verdict = rules.evaluate(self.order, trackers=[], semantic=None)

    def test_order_and_capture_id_present(self):
        self.assertEqual(self.verdict["order_id"], "2YD26664U8090205J")
        self.assertEqual(self.verdict["capture_id"], "4EC24563F7235632E")

    def test_ship_to_address_passes_when_address_present(self):
        c = checks_by_condition(self.verdict)["SHIP_TO_TRANSACTION_ADDRESS"]
        self.assertEqual(c["status"], "pass")

    def test_physical_goods_declared_passes(self):
        c = checks_by_condition(self.verdict)["PHYSICAL_GOODS_DECLARED"]
        self.assertEqual(c["status"], "pass")

    def test_high_value_signature_passes_under_threshold(self):
        c = checks_by_condition(self.verdict)["HIGH_VALUE_SIGNATURE"]
        self.assertEqual(c["status"], "pass")

    def test_tracking_required_fails_with_no_trackers(self):
        c = checks_by_condition(self.verdict)["TRACKING_REQUIRED"]
        self.assertEqual(c["status"], "fail")

    def test_flags_reflect_seller_protection(self):
        self.assertEqual(len(self.verdict["flags"]), 1)
        self.assertEqual(self.verdict["flags"][0]["status"], "ELIGIBLE")
        self.assertEqual(
            self.verdict["flags"][0]["dispute_categories"],
            ["ITEM_NOT_RECEIVED", "UNAUTHORIZED_TRANSACTION"],
        )

    def test_all_check_rows_have_expected_evidence(self):
        for c in self.verdict["checks"]:
            self.assertIn("expected_evidence", c)
            self.assertIsInstance(c["expected_evidence"], list)
            self.assertGreater(len(c["expected_evidence"]), 0, c["condition"])

    def test_all_check_rows_have_clause_and_prescription(self):
        for c in self.verdict["checks"]:
            self.assertTrue(c["clause"], c["condition"])
            self.assertTrue(c["prescription"], c["condition"])


class TestOrderCAutoInjectedAddress(unittest.TestCase):
    """Order C: shipping was omitted at checkout, but PayPal auto-injected the
    buyer's default address — the data shows a real address, so it must pass
    (measured finding: PayPal fills shipping.address when omitted)."""

    def setUp(self):
        self.order = load_order("order_C.json")
        self.verdict = rules.evaluate(self.order, trackers=[], semantic=None)

    def test_auto_injected_address_passes(self):
        c = checks_by_condition(self.verdict)["SHIP_TO_TRANSACTION_ADDRESS"]
        self.assertEqual(c["status"], "pass")


class TestOrderFNoAddress(unittest.TestCase):
    """Order F: NO_SHIPPING order — shipping is null, the true no-address case."""

    def setUp(self):
        self.order = load_order("order_F.json")
        self.verdict = rules.evaluate(self.order, trackers=[], semantic=None)

    def test_ship_to_address_fails_when_address_absent(self):
        c = checks_by_condition(self.verdict)["SHIP_TO_TRANSACTION_ADDRESS"]
        self.assertEqual(c["status"], "fail")

    def test_no_address_prescription_is_do_not_ship(self):
        c = checks_by_condition(self.verdict)["SHIP_TO_TRANSACTION_ADDRESS"]
        self.assertIn("Do not ship", c["prescription"])

    def test_basis_mentions_absent_shipping(self):
        c = checks_by_condition(self.verdict)["SHIP_TO_TRANSACTION_ADDRESS"]
        self.assertIn("absent", c["basis"].lower())


class TestOrderDHighValue(unittest.TestCase):
    """Order D: $800 capture — scenario #3, HIGH_VALUE_SIGNATURE must fail."""

    def setUp(self):
        self.order = load_order("order_D.json")
        self.verdict = rules.evaluate(self.order, trackers=[], semantic=None)

    def test_high_value_signature_fails_over_threshold(self):
        c = checks_by_condition(self.verdict)["HIGH_VALUE_SIGNATURE"]
        self.assertEqual(c["status"], "fail")
        self.assertIn("Use signature confirmation", c["prescription"])

    def test_high_value_no_signature_fraud_warning_present(self):
        names = {w["name"] for w in self.verdict["meaning"]["fraud_warnings"]}
        self.assertIn("HIGH_VALUE_NO_SIGNATURE", names)


class TestOrderBIntangible(unittest.TestCase):
    """Order B: DIGITAL_GOODS declared — scenario #6, never reported as fail."""

    def setUp(self):
        self.order = load_order("order_B.json")
        self.verdict = rules.evaluate(self.order, trackers=[], semantic=None)

    def test_intangible_row_is_not_assessable_not_fail(self):
        c = checks_by_condition(self.verdict)["INTANGIBLE_ADDITIONAL_REQS"]
        self.assertEqual(c["status"], "not_assessable")

    def test_physical_goods_declared_is_not_assessable_for_digital_item(self):
        c = checks_by_condition(self.verdict)["PHYSICAL_GOODS_DECLARED"]
        self.assertEqual(c["status"], "not_assessable")

    def test_intangible_row_never_fail_even_with_semantic_mismatch(self):
        semantic = {
            "category": "PHYSICAL",
            "confidence": 0.9,
            "mismatch": "DIGITAL_DECLARED_AS_PHYSICAL",
            "evidence_span": "item description says 'digital download'",
        }
        verdict = rules.evaluate(self.order, trackers=[], semantic=semantic)
        c = checks_by_condition(verdict)["INTANGIBLE_ADDITIONAL_REQS"]
        self.assertEqual(c["status"], "not_assessable")
        self.assertIn("digital download", c["basis"])


class TestSemanticMismatchMadeToOrder(unittest.TestCase):
    """Scenario #2: semantic mismatch drives SHIP_WITHIN_DAYS to fail + clause."""

    def setUp(self):
        self.order = load_order("order_A.json")

    def test_made_to_order_mismatch_fails_ship_within_days(self):
        semantic = {
            "category": "MADE_TO_ORDER",
            "confidence": 0.85,
            "mismatch": "MADE_TO_ORDER_DECLARED_AS_STOCK",
            "evidence_span": "listing says 'ships in 3-4 weeks, made to order'",
        }
        verdict = rules.evaluate(self.order, trackers=[], semantic=semantic)
        c = checks_by_condition(verdict)["SHIP_WITHIN_DAYS"]
        self.assertEqual(c["status"], "fail")
        self.assertIn("ships in 3-4 weeks", c["basis"])
        expected_clause = policy.MISMATCH_TO_CHECK["MADE_TO_ORDER_DECLARED_AS_STOCK"]["clause"]
        self.assertEqual(c["clause"], expected_clause)

    def test_ship_within_days_not_assessable_without_mismatch(self):
        verdict = rules.evaluate(self.order, trackers=[], semantic=None)
        c = checks_by_condition(verdict)["SHIP_WITHIN_DAYS"]
        self.assertEqual(c["status"], "not_assessable")


class TestSemanticNone(unittest.TestCase):
    """Scenario #8 degeneration path: no LLM available."""

    def setUp(self):
        self.order = load_order("order_A.json")
        self.verdict = rules.evaluate(self.order, trackers=[], semantic=None)

    def test_meaning_ran_is_false(self):
        self.assertFalse(self.verdict["meaning"]["ran"])

    def test_meaning_semantic_is_none(self):
        self.assertIsNone(self.verdict["meaning"]["semantic"])

    def test_semantic_dependent_check_remains_not_assessable_not_removed(self):
        c = checks_by_condition(self.verdict)["INTANGIBLE_ADDITIONAL_REQS"]
        self.assertEqual(c["status"], "not_assessable")

    def test_unassessable_patterns_returned_even_without_llm(self):
        patterns = self.verdict["meaning"]["unassessable_patterns"]
        self.assertGreaterEqual(len(patterns), 1)
        for p in patterns:
            self.assertFalse(p["api_assessable"])


class TestSummary(unittest.TestCase):
    def test_summary_counts_match_check_statuses(self):
        order = load_order("order_C.json")
        verdict = rules.evaluate(order, trackers=[], semantic=None)
        statuses = [c["status"] for c in verdict["checks"]]
        self.assertEqual(verdict["summary"]["n_pass"], statuses.count("pass"))
        self.assertEqual(verdict["summary"]["n_fail"], statuses.count("fail"))
        self.assertEqual(
            verdict["summary"]["n_not_assessable"], statuses.count("not_assessable")
        )
        self.assertEqual(
            sum(verdict["summary"].values()), len(verdict["checks"])
        )


class TestTrackingWithTracker(unittest.TestCase):
    def test_tracking_required_passes_when_tracker_has_number(self):
        order = load_order("order_A.json")
        trackers = [{"transaction_id": "4EC24563F7235632E", "tracking_number": "1Z999"}]
        verdict = rules.evaluate(order, trackers=trackers, semantic=None)
        c = checks_by_condition(verdict)["TRACKING_REQUIRED"]
        self.assertEqual(c["status"], "pass")

    def test_corrections_includes_register_tracking_when_tracking_fails(self):
        order = load_order("order_A.json")
        verdict = rules.evaluate(order, trackers=[], semantic=None)
        actions = {c["action"] for c in verdict["corrections"]}
        self.assertIn("REGISTER_TRACKING", actions)


if __name__ == "__main__":
    unittest.main()

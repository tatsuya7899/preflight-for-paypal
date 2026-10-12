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

    def test_high_value_signature_is_not_assessable_under_threshold(self):
        # fixed_status row: never pass/fail — signature confirmation is not a
        # requirement under current US terms (ver. 2026-01-26 audit)
        c = checks_by_condition(self.verdict)["HIGH_VALUE_SIGNATURE"]
        self.assertEqual(c["status"], "not_assessable")

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
    """Order D: $800 capture — signature confirmation was removed from the US
    terms (ver. 2026-01-26 audit): the row is now prescription-only and must
    report not_assessable even over the defensive $750 threshold."""

    def setUp(self):
        self.order = load_order("order_D.json")
        self.verdict = rules.evaluate(self.order, trackers=[], semantic=None)

    def test_high_value_signature_never_fails_over_threshold(self):
        c = checks_by_condition(self.verdict)["HIGH_VALUE_SIGNATURE"]
        self.assertEqual(c["status"], "not_assessable")
        self.assertIn("defensive practice", c["prescription"])

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


def _order_with_item(name, description=""):
    order = load_order("order_A.json")
    order["purchase_units"][0]["items"][0]["name"] = name
    order["purchase_units"][0]["items"][0]["description"] = description
    return order


def _excluded_check(name, description=""):
    verdict = rules.evaluate(
        _order_with_item(name, description), trackers=[], semantic=None
    )
    return checks_by_condition(verdict)["EXCLUDED_CATEGORY"]


class TestExcludedCategory(unittest.TestCase):
    """Audit S2: keyword heuristic against "Ineligible Items and Transactions"
    (ver. 2026-01-26). Word-boundary matching must not fire on partial words;
    phrase-level ambiguity stays a flag-with-visible-keyword by design."""

    def test_no_false_positive_partial_words(self):
        # Former substring matcher would fire on these (land/cash/car).
        for name in (
            "Handmade silk scarf from Thailand",
            "Cashmere sweater",
            "Care package gift box",
            "nftables-compatible utility knife",
        ):
            with self.subTest(name=name):
                self.assertEqual(_excluded_check(name)["status"], "pass")

    def test_business_phrase_does_not_flag_business_products(self):
        # Ineligible = the sale of a business, not items used for business.
        self.assertEqual(_excluded_check("Business card holder")["status"], "pass")
        c = _excluded_check("Online retail business for sale - turnkey")
        self.assertEqual(c["status"], "fail")
        self.assertIn("business for sale", c["basis"])

    def test_true_hits_still_fail_with_visible_keyword(self):
        for name, kw in (
            ("2019 Bayliner boat - freshwater use only", "boat"),
            ("Pre-owned motorcycle, low miles", "motorcycle"),
            ("NFT artwork - original mint", "nft"),
            ("Restaurant gift card $50", "gift card"),
        ):
            with self.subTest(name=name):
                c = _excluded_check(name)
                self.assertEqual(c["status"], "fail")
                self.assertIn(kw, c["basis"])

    def test_plural_and_hyphen_variants_still_fail(self):
        # Review fix (S2): \b alone missed plurals and separator variants.
        for name in (
            "Two motorcycles for sale - project bikes",
            "NFTs collection - original mints",
            "Restaurant gift-card $50",
            "Reloadable stored-value card",
            "Recreational vehicles and campers",
        ):
            with self.subTest(name=name):
                self.assertEqual(_excluded_check(name)["status"], "fail")

    def test_acceptable_use_policy_fires(self):
        c = _excluded_check("Knives per paypal's acceptable use policy")
        self.assertEqual(c["status"], "fail")

    def test_excluded_fail_is_marked_unfixable(self):
        c = _excluded_check("Pre-owned motorcycle, low miles")
        self.assertTrue(c.get("unfixable_for_order"))

    def test_excluded_prescription_says_verify(self):
        # Heuristic flag, not a definitive exclusion ruling.
        c = _excluded_check("2019 Bayliner boat - freshwater use only")
        self.assertIn("verify", c["prescription"].lower())


class TestFixedStatusEnforcement(unittest.TestCase):
    """evaluate() must apply a row's fixed_status over whatever the check
    function returned (review finding: no test exercised the loop itself —
    every check function happened to return the fixed value already)."""

    def test_evaluate_applies_fixed_status_over_check_result(self):
        row = policy.get_check("HIGH_VALUE_SIGNATURE")
        saved = row["fixed_status"]
        try:
            # Simulate a check function returning pass/fail by overriding the
            # policy row: evaluate() must still land on fixed_status.
            row["fixed_status"] = "fail"
            order = load_order("order_D.json")
            verdict = rules.evaluate(order, trackers=[], semantic=None)
            c = checks_by_condition(verdict)["HIGH_VALUE_SIGNATURE"]
            self.assertEqual(c["status"], "fail")
        finally:
            row["fixed_status"] = saved


if __name__ == "__main__":
    unittest.main()

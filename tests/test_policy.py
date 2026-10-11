"""Tests for backend/policy.py static policy data.

Test basis: SPEC-preflight-checker_design.md
  - "ルール層の条件表(US規約ピン)" section (CHECKS table)
  - "意味層の設計" section (mismatch mapping, fraud patterns)
  - データモデル・インターフェース section (expected_evidence field)
Written from the design spec's tables, not from reading policy.py's implementation.
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import policy


EXPECTED_CONDITIONS = {
    "SHIP_TO_TRANSACTION_ADDRESS",
    "TRACKING_REQUIRED",
    "PHYSICAL_GOODS_DECLARED",
    "INTANGIBLE_ADDITIONAL_REQS",
    "HIGH_VALUE_SIGNATURE",
    "SHIP_WITHIN_DAYS",
    "EXCLUDED_CATEGORY",
}

REQUIRED_KEYS = {
    "condition",
    "input_path",
    "clause",
    "prescription",
    "expected_evidence",
}


class TestChecksTable(unittest.TestCase):
    def test_checks_table_exists_and_is_list(self):
        self.assertTrue(hasattr(policy, "CHECKS"))
        self.assertIsInstance(policy.CHECKS, list)

    def test_all_expected_conditions_present(self):
        names = {row["condition"] for row in policy.CHECKS}
        self.assertEqual(names, EXPECTED_CONDITIONS)

    def test_each_row_has_required_keys(self):
        for row in policy.CHECKS:
            missing = REQUIRED_KEYS - set(row.keys())
            self.assertEqual(missing, set(), f"{row.get('condition')} missing keys {missing}")

    def test_each_row_clause_and_prescription_nonempty(self):
        for row in policy.CHECKS:
            self.assertTrue(row["clause"], row["condition"])
            self.assertTrue(row["prescription"], row["condition"])

    def test_intangible_row_status_fixed_not_assessable(self):
        row = policy.get_check("INTANGIBLE_ADDITIONAL_REQS")
        self.assertEqual(row.get("fixed_status"), "not_assessable")

    def test_high_value_signature_threshold_750(self):
        self.assertEqual(policy.HIGH_VALUE_SIGNATURE_THRESHOLD_USD, 750)

    def test_each_condition_expected_evidence_nonempty(self):
        for row in policy.CHECKS:
            self.assertIsInstance(row["expected_evidence"], list)
            self.assertGreater(len(row["expected_evidence"]), 0, row["condition"])


class TestMismatchMapping(unittest.TestCase):
    def test_mismatch_mapping_exists(self):
        self.assertTrue(hasattr(policy, "MISMATCH_TO_CHECK"))

    def test_digital_declared_as_physical_maps_to_intangible(self):
        entry = policy.MISMATCH_TO_CHECK["DIGITAL_DECLARED_AS_PHYSICAL"]
        self.assertEqual(entry["check"], "INTANGIBLE_ADDITIONAL_REQS")
        self.assertTrue(entry.get("clause"))

    def test_made_to_order_declared_as_stock_maps_to_ship_within_days(self):
        entry = policy.MISMATCH_TO_CHECK["MADE_TO_ORDER_DECLARED_AS_STOCK"]
        self.assertEqual(entry["check"], "SHIP_WITHIN_DAYS")
        self.assertTrue(entry.get("clause"))

    def test_mismatch_mapping_has_exactly_two_keys(self):
        self.assertEqual(
            set(policy.MISMATCH_TO_CHECK.keys()),
            {"DIGITAL_DECLARED_AS_PHYSICAL", "MADE_TO_ORDER_DECLARED_AS_STOCK"},
        )


class TestCarrierEnum(unittest.TestCase):
    def test_carrier_enum_contains_other(self):
        self.assertIn("OTHER", policy.CARRIERS)

    def test_carrier_enum_contains_major_carriers(self):
        for c in ("UPS", "USPS", "FEDEX", "DHL"):
            self.assertIn(c, policy.CARRIERS)

    def test_other_requires_carrier_name_other_flag(self):
        self.assertTrue(policy.CARRIER_OTHER_REQUIRES_NAME)


class TestExcludedCategories(unittest.TestCase):
    def test_excluded_keywords_nonempty(self):
        self.assertIsInstance(policy.EXCLUDED_CATEGORY_KEYWORDS, list)
        self.assertGreater(len(policy.EXCLUDED_CATEGORY_KEYWORDS), 0)

    def test_excluded_keywords_contain_vehicle_and_real_estate(self):
        joined = " ".join(policy.EXCLUDED_CATEGORY_KEYWORDS).lower()
        self.assertIn("vehicle", joined)
        self.assertTrue("real estate" in joined or "real-estate" in joined)


class TestFraudPatterns(unittest.TestCase):
    def test_fraud_patterns_table_exists(self):
        self.assertIsInstance(policy.FRAUD_PATTERNS, list)
        self.assertGreater(len(policy.FRAUD_PATTERNS), 0)

    def test_each_fraud_pattern_has_assessability_flag(self):
        for p in policy.FRAUD_PATTERNS:
            self.assertIn("name", p)
            self.assertIn("api_assessable", p)
            self.assertIsInstance(p["api_assessable"], bool)

    def test_unassessable_patterns_filter_helper(self):
        unassessable = policy.unassessable_patterns()
        self.assertGreaterEqual(len(unassessable), 1)
        for p in unassessable:
            self.assertFalse(p["api_assessable"])

    def test_at_least_one_pattern_is_api_assessable(self):
        assessable = [p for p in policy.FRAUD_PATTERNS if p["api_assessable"]]
        self.assertGreaterEqual(len(assessable), 1)


class TestExpectedEvidenceMapping(unittest.TestCase):
    def test_tracking_required_maps_to_proof_of_fulfillment(self):
        row = policy.get_check("TRACKING_REQUIRED")
        self.assertIn("PROOF_OF_FULFILLMENT", row["expected_evidence"])


if __name__ == "__main__":
    unittest.main()

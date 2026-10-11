"""Static policy data for preflight-checker.

Source of truth: SPEC-preflight-checker_design.md
  - "ルール層の条件表(US規約ピン)" (CHECKS)
  - "意味層の設計" (MISMATCH_TO_CHECK, FRAUD_PATTERNS)
  - データモデル・インターフェース (expected_evidence per check)

All strings are in English (UI language = English only per requirements doc).
This module holds no behaviour beyond small lookup helpers — the decision logic
that consumes this data lives in backend/rules.py and backend/meaning.py.
"""

# US Seller Protection signature-confirmation threshold (paypal.com/us/legalhub +
# seller-protection PDF, confirmed in design doc P2-3).
HIGH_VALUE_SIGNATURE_THRESHOLD_USD = 750

# PayPal evidence types a seller may be asked to produce in a dispute, referenced
# from each check row's `expected_evidence`. Vocabulary matches the US dispute /
# claim evidence categories (tracking, proof of fulfillment, proof of delivery, etc.).
EVIDENCE_PROOF_OF_FULFILLMENT = "PROOF_OF_FULFILLMENT"
EVIDENCE_PROOF_OF_DELIVERY_ADDRESS = "PROOF_OF_DELIVERY_ADDRESS"
EVIDENCE_TRACKING_INFORMATION = "TRACKING_INFORMATION"
EVIDENCE_SIGNATURE_CONFIRMATION = "SIGNATURE_CONFIRMATION"
EVIDENCE_PROOF_OF_SERVICE_OR_DELIVERY_LOG = "PROOF_OF_SERVICE_OR_DELIVERY_LOG"
EVIDENCE_ITEM_DESCRIPTION_OR_LISTING = "ITEM_DESCRIPTION_OR_LISTING"
EVIDENCE_SHIPMENT_DATE_RECORD = "SHIPMENT_DATE_RECORD"
EVIDENCE_CATEGORY_DOCUMENTATION = "CATEGORY_DOCUMENTATION"

# Condition table (CHECKS). Each row describes one rule-layer check:
#   condition      : stable machine name (verdict["checks"][*]["condition"])
#   input_path     : where in the PayPal API response the judgement input lives
#   clause         : US Seller Protection terms clause/section reference
#   prescription   : fixed English prescription string shown on fail
#   expected_evidence : PayPal evidence types that may later be demanded in a dispute
#   fixed_status   : optional. If set, this check's status is always this value
#                     regardless of evaluation (used for INTANGIBLE_ADDITIONAL_REQS,
#                     which is prescription-only per design doc — never "fail").
#   unfixable_for_order : optional. If true, a "fail" verdict on this check
#                     cannot be remedied for the order being viewed — its
#                     referenced evidence slots are unfillable (UI annotation).
CHECKS = [
    {
        "condition": "SHIP_TO_TRANSACTION_ADDRESS",
        "input_path": "purchase_units[].shipping",
        "clause": "US Seller Protection terms \u00a71(a) — Shipped to the address on the Transaction",
        "prescription": (
            "Do not ship — obtain the buyer's confirmed address via a new transaction"
        ),
        "prescription_address_mismatch": "Ship only to the address on the transaction",
        "unfixable_for_order": True,
        "expected_evidence": [
            EVIDENCE_PROOF_OF_DELIVERY_ADDRESS,
            EVIDENCE_TRACKING_INFORMATION,
        ],
    },
    {
        "condition": "TRACKING_REQUIRED",
        "input_path": "GET /v1/shipping/trackers?transaction_id=",
        "clause": "US Seller Protection terms \u00a71(b) — Proof of shipment or delivery",
        "prescription": "Add tracking — button (REGISTER_TRACKING)",
        "expected_evidence": [
            EVIDENCE_PROOF_OF_FULFILLMENT,
            EVIDENCE_TRACKING_INFORMATION,
        ],
    },
    {
        "condition": "PHYSICAL_GOODS_DECLARED",
        "input_path": "items[].category",
        "clause": "US Seller Protection terms \u00a71 — Eligible item types (Physical Goods)",
        "prescription": (
            "Item is not declared as physical goods — evaluate under the "
            "Intangible Goods Additional Requirements path instead"
        ),
        "expected_evidence": [
            EVIDENCE_ITEM_DESCRIPTION_OR_LISTING,
        ],
    },
    {
        "condition": "INTANGIBLE_ADDITIONAL_REQS",
        "input_path": "meaning.semantic.category",
        "clause": "US Seller Protection terms — Intangible Goods Additional Requirements",
        "prescription": (
            "Keep fulfillment logs/proof of service delivery per US Intangible "
            "Goods Additional Requirements"
        ),
        "expected_evidence": [
            EVIDENCE_PROOF_OF_SERVICE_OR_DELIVERY_LOG,
        ],
        # Fixed per design doc: this row is prescription-only and must never be
        # reported as "fail" ("digital = categorically excluded" is the wrong
        # rule this check exists to prevent reproducing).
        "fixed_status": "not_assessable",
    },
    {
        # Clause basis pinned to the legalhub threshold table (750 USD).
        # NOTE: PayPal PM help text states signature confirmation became
        # "recommended, not mandatory" for transactions on/after 2026-01-26
        # while the legalhub table still lists the threshold — version drift.
        # Re-verify the current US version before submission (M2/M7 finding).
        "condition": "HIGH_VALUE_SIGNATURE",
        "input_path": "purchase_units[].amount.value (>= $750 USD)",
        "clause": "US Seller Protection terms \u00a71(c) — Signature Confirmation for high-value items (legalhub threshold table, 750 USD)",
        "prescription": "Use signature confirmation",
        "expected_evidence": [
            EVIDENCE_SIGNATURE_CONFIRMATION,
        ],
    },
    {
        "condition": "SHIP_WITHIN_DAYS",
        "input_path": "order.create_time",
        "clause": "US Seller Protection terms \u00a71(d) — Timely shipment window",
        # US terms: required only for pre-ordered / made-to-order goods (ship
        # within the timeframe specified in the listing); otherwise "it is
        # recommended" to ship within 7 days — not a hard requirement.
        "prescription": "Ship within your stated timeframe (required for pre-order/made-to-order); otherwise recommended within 7 days",
        "expected_evidence": [
            EVIDENCE_SHIPMENT_DATE_RECORD,
            EVIDENCE_PROOF_OF_FULFILLMENT,
        ],
    },
    {
        "condition": "EXCLUDED_CATEGORY",
        "input_path": "items[].name / items[].description",
        "clause": "US Seller Protection terms \u00a72 — Excluded item categories",
        "prescription": "Category excluded from Seller Protection",
        "unfixable_for_order": True,
        "expected_evidence": [
            EVIDENCE_CATEGORY_DOCUMENTATION,
        ],
    },
]


def get_check(condition_name):
    """Return the CHECKS row for condition_name, or None if not found."""
    for row in CHECKS:
        if row["condition"] == condition_name:
            return row
    return None


# Semantic mismatch -> check-row mapping (meaning layer, design doc P1-2a).
# Used when the LLM-dependent semantic classifier detects an explicit, undisputed
# mismatch between declared category and item description.
MISMATCH_TO_CHECK = {
    "DIGITAL_DECLARED_AS_PHYSICAL": {
        "check": "INTANGIBLE_ADDITIONAL_REQS",
        "clause": "US Seller Protection terms — Intangible Goods Additional Requirements",
    },
    "MADE_TO_ORDER_DECLARED_AS_STOCK": {
        "check": "SHIP_WITHIN_DAYS",
        "clause": "US Seller Protection terms \u00a71(d) — Timely shipment window",
    },
}

# Carrier enum for the tracking-registration correction form (panel.js).
CARRIERS = ["UPS", "USPS", "FEDEX", "DHL", "OTHER"]

# When carrier == "OTHER", the caller (panel.js / /track handler) must also
# supply carrier_name_other.
CARRIER_OTHER_REQUIRES_NAME = True

# PayPal Seller Protection excluded-category keywords (policy.py static list,
# per design doc "EXCLUDED_CATEGORY" row). Matched case-insensitively against
# items[].name / items[].description.
EXCLUDED_CATEGORY_KEYWORDS = [
    "vehicle",
    "motor vehicle",
    "car",
    "motorcycle",
    "boat",
    "aircraft",
    "real estate",
    "real-estate",
    "land",
    "property (real estate)",
    "business",
    "industrial equipment",
    "custom-made item",
    "item that violates paypal's acceptable use policy",
    "cash",
    "cash equivalent",
    "gift card",
    "travel ticket",
    "ticket for an event",
    "donation",
]

# Fraud pattern table: PayPal-documented Seller Protection fraud patterns mapped
# to whether an API-visible signal exists to assess them (design doc "意味層の
# 設計" / FR-2). Patterns relying on signals not exposed by the Orders/Tracking
# API (e.g. buyer behavioral history, device fingerprint) are api_assessable=False
# and surface under meaning.unassessable_patterns rather than being silently
# dropped or guessed at.
FRAUD_PATTERNS = [
    {
        "name": "NO_SHIPPING_ADDRESS_ON_FILE",
        "description": (
            "Transaction has no shipping address at all, a pattern PayPal "
            "documents in Item Not Received disputes where the seller cannot "
            "prove any delivery address was ever confirmed."
        ),
        "api_assessable": True,
        "signal_basis": "purchase_units[].shipping absent on this order",
    },
    {
        "name": "HIGH_VALUE_NO_SIGNATURE",
        "description": (
            "High-value item shipped without signature confirmation, a pattern "
            "PayPal documents as increasing Unauthorized Transaction exposure."
        ),
        "api_assessable": True,
        "signal_basis": "amount.value >= $750 USD with no signature-confirmation tracker",
    },
    {
        "name": "MISMATCHED_SHIP_TO_VS_BILLING_COUNTRY",
        "description": (
            "Shipping address country differs from the payer's billing/country "
            "of residence, a pattern PayPal documents in cross-border fraud "
            "advisories."
        ),
        "api_assessable": False,
        "signal_basis": "payer billing country is not exposed by the Orders API response used here",
    },
    {
        "name": "RAPID_REPEAT_HIGH_VALUE_BUYER",
        "description": (
            "Same buyer places multiple high-value orders in a short window, "
            "a pattern PayPal documents as account-takeover risk."
        ),
        "api_assessable": False,
        "signal_basis": "requires cross-order buyer history, not available from a single capture/order lookup",
    },
    {
        "name": "FIRST_TIME_BUYER_EXPEDITED_SHIPPING_REQUEST",
        "description": (
            "First-time buyer requesting expedited/overnight shipping on a "
            "high-value item, a pattern PayPal documents as a fraud indicator."
        ),
        "api_assessable": False,
        "signal_basis": "buyer transaction history and shipping-speed preference are not exposed by this API",
    },
]


def unassessable_patterns():
    """Return the subset of FRAUD_PATTERNS that cannot be assessed from API-visible signals."""
    return [p for p in FRAUD_PATTERNS if not p["api_assessable"]]


def assessable_patterns():
    """Return the subset of FRAUD_PATTERNS that can be assessed from API-visible signals."""
    return [p for p in FRAUD_PATTERNS if p["api_assessable"]]

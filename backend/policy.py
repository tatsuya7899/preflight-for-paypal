"""Static policy data for preflight-checker.

Source of truth: SPEC-preflight-checker_design.md
  - "ルール層の条件表(US規約ピン)" (CHECKS)
  - "意味層の設計" (MISMATCH_TO_CHECK, FRAUD_PATTERNS)
  - データモデル・インターフェース (expected_evidence per check)

All strings are in English (UI language = English only per requirements doc).
This module holds no behaviour beyond small lookup helpers — the decision logic
that consumes this data lives in backend/rules.py and backend/meaning.py.
"""

# Policy source pinned by audit (S2, 2026-10-12):
#   Document: PayPal's Seller Protection Program (US)
#   URL:      https://www.paypal.com/us/legalhub/paypal/seller-protection
#   Version:  "Last updated on January 26, 2026"
# The document has NO numbered clauses — it uses named sections. Every
# `clause` string below cites the real section name, not an invented "§N":
#   "What's Eligible", "Basic Requirements", "Item Not Received Additional
#   Requirement", "Intangible Goods Additional Requirements", "Establishing
#   Proof of Shipment or Proof of Delivery", "Ineligible Items and
#   Transactions".
POLICY_DOC_NAME = "US Seller Protection Program terms"
POLICY_DOC_VERSION = "2026-01-26"
POLICY_DOC_URL = "https://www.paypal.com/us/legalhub/paypal/seller-protection"

# Signature-confirmation threshold. The $750 requirement exists in OTHER
# regions' terms (SEA/CEMEA) but is ABSENT from the current US document
# (ver. 2026-01-26) — verified 2026-10-12 audit: the string "signature" does
# not appear in the US terms at all. Retained as a defensive-practice
# heuristic only; the HIGH_VALUE_SIGNATURE check must never report "fail".
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
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Basic Requirements: ship to the shipping address on the Transaction Details page",
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
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Basic Requirements: valid proof of shipment or delivery (verifiable tracking number)",
        "prescription": "Add tracking — button (REGISTER_TRACKING)",
        "expected_evidence": [
            EVIDENCE_PROOF_OF_FULFILLMENT,
            EVIDENCE_TRACKING_INFORMATION,
        ],
    },
    {
        "condition": "PHYSICAL_GOODS_DECLARED",
        "input_path": "items[].category",
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Basic Requirements: item must be a physical, tangible good that can be shipped",
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
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Intangible Goods Additional Requirements",
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
        # AUDIT (S2, 2026-10-12): signature confirmation is NOT required by the
        # current US terms — the string does not appear anywhere in the
        # 2026-01-26 document. The $750 table survives only in other regions'
        # terms (SEA/CEMEA). This row is therefore prescription-only
        # (fixed_status), never "fail": flagging it as a violation would be a
        # fabricated requirement.
        "condition": "HIGH_VALUE_SIGNATURE",
        "input_path": "purchase_units[].amount.value (>= $750 USD)",
        "clause": "US Seller Protection terms (ver. 2026-01-26) — no signature-confirmation requirement present (defensive practice; $750 threshold exists only in non-US terms)",
        "prescription": "Signature confirmation is a defensive practice for high-value orders — not required by current US Seller Protection terms",
        "fixed_status": "not_assessable",
        "expected_evidence": [
            EVIDENCE_SIGNATURE_CONFIRMATION,
        ],
    },
    {
        "condition": "SHIP_WITHIN_DAYS",
        "input_path": "order.create_time",
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Basic Requirements: ship within the listing-specified timeframe for pre-ordered/made-to-order goods; recommended within 7 days otherwise",
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
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Ineligible Items and Transactions",
        # Keyword match is a heuristic flag, not a definitive exclusion — the
        # prescription says "verify" so the seller checks the actual list.
        "prescription": "Item text matches a Seller-Protection-ineligible category — verify against Ineligible Items and Transactions",
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
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Intangible Goods Additional Requirements",
    },
    "MADE_TO_ORDER_DECLARED_AS_STOCK": {
        "check": "SHIP_WITHIN_DAYS",
        "clause": "US Seller Protection terms (ver. 2026-01-26) — Basic Requirements: ship within the listing-specified timeframe for pre-ordered/made-to-order goods",
    },
}

# Carrier enum for the tracking-registration correction form (panel.js).
CARRIERS = ["UPS", "USPS", "FEDEX", "DHL", "OTHER"]

# When carrier == "OTHER", the caller (panel.js / /track handler) must also
# supply carrier_name_other.
CARRIER_OTHER_REQUIRES_NAME = True

# PayPal Seller Protection ineligible-category keywords, aligned by audit
# (S2, 2026-10-12) to the "Ineligible Items and Transactions" section of the
# US terms ver. 2026-01-26. Matched case-insensitively at word boundaries
# against items[].name / items[].description. Text and keywords are
# separator-normalized (hyphens/whitespace -> single space) and a trailing
# plural "s" is tolerated, so "gift-card", "NFTs", "motorcycles" all match —
# a heuristic, documented in the check basis when it fires. Phrase-level
# false positives remain possible by design (e.g. "boat shoes" still matches
# "boat", "motorcycle helmet" matches "motorcycle"): the check is a flag for
# the seller's own verification, not a definitive exclusion ruling — the
# matched keyword is always shown in the basis.
#
# Audit removals:
#   - "custom-made item"      : NOT ineligible — made-to-order only carries a
#                               listing-timeframe shipment rule (eligible).
#   - "ticket for an event"   : NOT ineligible — the only ticketing exclusion
#                               is travel tickets under a narrow claim-timing
#                               condition (UT claim >24h before travel date),
#                               which item text cannot assess.
#   - "travel ticket"         : same — conditionally excluded only.
#   - "car"                   : substring matches "care"/"cargo"/"card" —
#                               vehicle/motor vehicle/motorcycle cover it.
#   - "land"                  : substring matches "Thailand"/"Iceland" etc.
#   - "cash"                  : substring matches "cashmere".
#   - "gold"                  : the exclusion covers gold-as-commodity, not
#                               "gold necklace" (a normal physical good).
#   - "property (real estate)": literal parens never match real text;
#                               real-estate/residential property cover it.
# Known limits: NFT exclusion is amount-gated (>=$10,000.01 always excluded;
# <=$10,000.00 excluded except qualifying UT claims) — keyword flags the
# category, the amount nuance is documented in the check basis/comment.
EXCLUDED_CATEGORY_KEYWORDS = [
    # Vehicles (light portable vehicles like bicycles/hoverboards are excepted
    # in the terms — keyword-level nuance not assessable from item text)
    "vehicle",
    "motor vehicle",
    "motorcycle",
    "recreational vehicle",
    "boat",
    "aircraft",
    # Real estate / businesses / industrial machinery
    "real estate",
    "real-estate",
    "residential property",
    # Ineligible item = the sale of a business itself; bare "business" would
    # flag "business card holder" / "business casual" products.
    "business for sale",
    "industrial equipment",
    "industrial machinery",
    # Cash equivalents / stored value / financial products
    "cash equivalent",
    "gift card",
    "prepaid card",
    "pre-paid card",
    "stored value",
    "investment",
    # NFTs (excluded; <=$10k carve-out for qualifying UT claims — see comment)
    "nft",
    "non-fungible",
    # Gambling (entry fee + prize activities)
    "gambling",
    "casino",
    "lottery",
    # Donations / crowdfunding
    "donation",
    "crowdfunding",
    # Bill payment services
    "bill payment",
    # PayPal Acceptable Use violations — short form so it actually fires;
    # a literal "item that violates..." sentence never appears in listings.
    "acceptable use policy",
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
            "High-value item shipped without signature confirmation — a "
            "defensive practice (not a requirement under current US terms "
            "ver. 2026-01-26; $750 is the non-US/historical threshold)."
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

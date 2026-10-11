"""Deterministic rule layer + verdict assembly for preflight-checker.

Design source: SPEC-preflight-checker_design.md
  - "ルール層の条件表(US規約ピン)" (per-check evaluation logic)
  - "データモデル・インターフェース" (verdict schema)
  - "意味層の設計" (semantic mismatch -> check-row mapping, fraud patterns)

This module does not call any LLM. `semantic` (the meaning-layer LLM output) is
received as a plain argument — evaluate() is pure and deterministic given its
three inputs (order, trackers, semantic).
"""
from backend import policy


def _amount_value(purchase_unit):
    amount = (purchase_unit.get("amount") or {}).get("value")
    if amount is None:
        return None
    try:
        return float(amount)
    except (TypeError, ValueError):
        return None


def _first_item(purchase_unit):
    items = purchase_unit.get("items") or []
    return items[0] if items else None


def _row(condition, status, basis):
    """Build a check-row dict from a policy.CHECKS template + computed status/basis."""
    template = policy.get_check(condition)
    return {
        "condition": condition,
        "status": status,
        "basis": basis,
        "clause": template["clause"],
        "prescription": template["prescription"],
        "expected_evidence": list(template["expected_evidence"]),
        "unfixable_for_order": bool(template.get("unfixable_for_order")),
    }


def _check_ship_to_address(order, purchase_unit):
    shipping = purchase_unit.get("shipping")
    if not shipping or not shipping.get("address"):
        return _row(
            "SHIP_TO_TRANSACTION_ADDRESS",
            "fail",
            "purchase_units[].shipping is absent — no confirmed address on the transaction",
        )

    return _row(
        "SHIP_TO_TRANSACTION_ADDRESS",
        "pass",
        "purchase_units[].shipping.address present",
    )


def _check_tracking_required(trackers):
    trackers = trackers or []
    numbered = [t for t in trackers if t.get("tracking_number")]
    if numbered:
        return _row(
            "TRACKING_REQUIRED",
            "pass",
            f"{len(numbered)} tracker(s) with a tracking_number found",
        )
    return _row(
        "TRACKING_REQUIRED",
        "fail",
        "no trackers with a tracking_number found for this capture",
    )


def _check_physical_goods(purchase_unit):
    item = _first_item(purchase_unit)
    if item is None:
        return _row(
            "PHYSICAL_GOODS_DECLARED",
            "not_assessable",
            "no items[] array present on purchase_units[]",
        )
    category = item.get("category")
    if category == "PHYSICAL_GOODS":
        return _row(
            "PHYSICAL_GOODS_DECLARED",
            "pass",
            f"items[0].category={category}",
        )
    # Non-physical declared category routes to the intangible-goods path;
    # this row itself is never "fail" per design doc.
    return _row(
        "PHYSICAL_GOODS_DECLARED",
        "not_assessable",
        f"items[0].category={category!r} — not declared as physical goods, "
        "evaluate under INTANGIBLE_ADDITIONAL_REQS instead",
    )


def _check_intangible(purchase_unit, semantic):
    """Always not_assessable (fixed_status) — prescription-only row."""
    item = _first_item(purchase_unit)
    declared_category = item.get("category") if item else None

    mismatch_entry = None
    if semantic and semantic.get("mismatch") == "DIGITAL_DECLARED_AS_PHYSICAL":
        mismatch_entry = policy.MISMATCH_TO_CHECK["DIGITAL_DECLARED_AS_PHYSICAL"]

    if mismatch_entry is not None:
        basis = (
            f"meaning.semantic.mismatch=DIGITAL_DECLARED_AS_PHYSICAL "
            f"(evidence: {semantic.get('evidence_span')!r})"
        )
    elif semantic and semantic.get("category") in ("DIGITAL", "SERVICE"):
        basis = f"meaning.semantic.category={semantic.get('category')}"
    elif declared_category not in (None, "PHYSICAL_GOODS"):
        basis = f"items[0].category={declared_category!r}"
    elif semantic is None:
        basis = "not evaluated: meaning layer did not run (meaning.ran=false)"
    else:
        basis = "no digital/service signal present"

    row = _row("INTANGIBLE_ADDITIONAL_REQS", "not_assessable", basis)
    if mismatch_entry is not None:
        row["clause"] = mismatch_entry["clause"]
    return row


def _check_high_value_signature(purchase_unit):
    amount = _amount_value(purchase_unit)
    threshold = policy.HIGH_VALUE_SIGNATURE_THRESHOLD_USD
    if amount is None:
        return _row(
            "HIGH_VALUE_SIGNATURE",
            "not_assessable",
            "purchase_units[].amount.value not present",
        )
    if amount >= threshold:
        return _row(
            "HIGH_VALUE_SIGNATURE",
            "fail",
            f"amount.value={amount} USD >= ${threshold} threshold, "
            "no signature-confirmation data present",
        )
    return _row(
        "HIGH_VALUE_SIGNATURE",
        "pass",
        f"amount.value={amount} USD < ${threshold} threshold",
    )


def _check_ship_within_days(purchase_unit, semantic):
    mismatch_entry = None
    if semantic and semantic.get("mismatch") == "MADE_TO_ORDER_DECLARED_AS_STOCK":
        mismatch_entry = policy.MISMATCH_TO_CHECK["MADE_TO_ORDER_DECLARED_AS_STOCK"]

    if mismatch_entry is not None:
        row = _row(
            "SHIP_WITHIN_DAYS",
            "fail",
            f"meaning.semantic.mismatch=MADE_TO_ORDER_DECLARED_AS_STOCK "
            f"(evidence: {semantic.get('evidence_span')!r})",
        )
        row["clause"] = mismatch_entry["clause"]
        return row

    # No shipment/ship-by date is exposed by the Orders API response used here,
    # so the remaining-window computation has no signal to work from.
    return _row(
        "SHIP_WITHIN_DAYS",
        "not_assessable",
        "no shipment date recorded yet; cannot compute remaining shipment window",
    )


def _check_excluded_category(purchase_unit):
    item = _first_item(purchase_unit)
    if item is None:
        return _row(
            "EXCLUDED_CATEGORY",
            "not_assessable",
            "no items[] array present on purchase_units[]",
        )
    text = f"{item.get('name', '')} {item.get('description', '')}".lower()
    for keyword in policy.EXCLUDED_CATEGORY_KEYWORDS:
        if keyword in text:
            return _row(
                "EXCLUDED_CATEGORY",
                "fail",
                f"items[0].name/description matched excluded keyword {keyword!r}",
            )
    return _row(
        "EXCLUDED_CATEGORY",
        "pass",
        "items[0].name/description matched no excluded-category keyword",
    )


def _fraud_warnings(purchase_unit, trackers):
    """Table-driven, API-visible-signal-only fraud pattern matches (no LLM)."""
    warnings = []
    for pattern in policy.assessable_patterns():
        name = pattern["name"]
        if name == "NO_SHIPPING_ADDRESS_ON_FILE":
            shipping = purchase_unit.get("shipping")
            if not shipping or not shipping.get("address"):
                warnings.append({"name": name, "signal_basis": pattern["signal_basis"]})
        elif name == "HIGH_VALUE_NO_SIGNATURE":
            amount = _amount_value(purchase_unit)
            if amount is not None and amount >= policy.HIGH_VALUE_SIGNATURE_THRESHOLD_USD:
                warnings.append({"name": name, "signal_basis": pattern["signal_basis"]})
    return warnings


def evaluate(order, trackers, semantic=None):
    """Evaluate one order against the rule layer and assemble a verdict dict.

    Args:
        order: dict, the GET /v2/checkout/orders/{id} response shape (see
            backend/fixtures/order_*.json).
        trackers: list of tracker dicts (GET /v1/shipping/trackers response's
            "trackers" list), or None/empty if none registered.
        semantic: dict|None, the meaning-layer LLM output (see design doc
            "データモデル・インターフェース" -> meaning.semantic), or None when
            the meaning layer did not run (no LLM key / runtime failure).

    Returns:
        A verdict dict per the design doc's "データモデル・インターフェース" schema.
    """
    trackers = trackers or []
    order_id = order.get("id")
    purchase_units = order.get("purchase_units") or [{}]
    purchase_unit = purchase_units[0]
    captures = (purchase_unit.get("payments") or {}).get("captures") or [{}]

    flags = []
    for capture in captures:
        sp = capture.get("seller_protection")
        if sp:
            flags.append({
                "capture_id": capture.get("id"),
                "status": sp.get("status"),
                "dispute_categories": sp.get("dispute_categories"),
            })
        else:
            flags.append({"capture_id": capture.get("id"), "status": None})

    capture_id = captures[0].get("id")

    checks = [
        _check_ship_to_address(order, purchase_unit),
        _check_tracking_required(trackers),
        _check_physical_goods(purchase_unit),
        _check_intangible(purchase_unit, semantic),
        _check_high_value_signature(purchase_unit),
        _check_ship_within_days(purchase_unit, semantic),
        _check_excluded_category(purchase_unit),
    ]

    summary = {
        "n_pass": sum(1 for c in checks if c["status"] == "pass"),
        "n_fail": sum(1 for c in checks if c["status"] == "fail"),
        "n_not_assessable": sum(1 for c in checks if c["status"] == "not_assessable"),
    }

    meaning = {
        "ran": semantic is not None,
        "semantic": semantic,
        "fraud_warnings": _fraud_warnings(purchase_unit, trackers),
        "unassessable_patterns": policy.unassessable_patterns(),
    }

    corrections = []
    tracking_check = next(c for c in checks if c["condition"] == "TRACKING_REQUIRED")
    if tracking_check["status"] == "fail":
        corrections.append({
            "action": "REGISTER_TRACKING",
            "label": "Add tracking to this order",
        })

    return {
        "order_id": order_id,
        "capture_id": capture_id,
        "flags": flags,
        "summary": summary,
        "checks": checks,
        "meaning": meaning,
        "corrections": corrections,
    }

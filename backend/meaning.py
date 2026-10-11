"""Meaning layer for preflight-checker.

Source of truth: SPEC-preflight-checker_design.md, "意味層の設計" section.

Two deliberately separate parts (P1-2/P1-3 of the design doc):
  1. ``semantic`` classification — LLM-dependent. Classifies item description
     text into a fixed enum (DIGITAL/PHYSICAL/SERVICE/MADE_TO_ORDER/PRE_ORDER)
     and flags only *undisputed* mismatches against the declared category.
  2. ``fraud`` pattern matching — table-driven, no LLM. Matches PayPal's
     documented Seller Protection fraud patterns (backend/policy.py
     FRAUD_PATTERNS) against API-visible signals in the order.

The LLM is instructed to classify only — never to interpret policy clauses,
generate prescriptions, or predict dispute outcomes (design doc AI #2 /
"LLMへの指示は分類のみ"). Prescriptions always come from policy.py's fixed
tables.

``run(order)`` never raises: if the LLM is unavailable or fails at runtime
(missing key, network error, timeout, bad JSON), it degrades to
``ran=False, semantic=None`` while still returning the table-driven fraud
results (design doc FR-8 / P2-6).
"""
import json
import os
import urllib.error
import urllib.request

from backend import policy

SEMANTIC_CATEGORIES = {"DIGITAL", "PHYSICAL", "SERVICE", "MADE_TO_ORDER", "PRE_ORDER"}

ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
GEMINI_MODEL = "gemini-1.5-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

_SYSTEM_PROMPT = (
    "You classify e-commerce item descriptions into exactly one category: "
    "DIGITAL, PHYSICAL, SERVICE, MADE_TO_ORDER, or PRE_ORDER. "
    "You do not interpret seller protection policy clauses, you do not write "
    "prescriptions or remediation advice, and you do not predict dispute "
    "outcomes. Only flag a mismatch between the declared category and the "
    "description when the description explicitly and unambiguously states a "
    "different category (e.g. the description literally says 'digital "
    "download' while the item is declared as physical goods). If the "
    "description is ambiguous, set mismatch to null. "
    "Respond with ONLY a JSON object, no other text, in this exact shape: "
    '{"category": "<one of the five enum values>", "confidence": <0..1 float>, '
    '"mismatch": null or one of ["DIGITAL_DECLARED_AS_PHYSICAL", '
    '"MADE_TO_ORDER_DECLARED_AS_STOCK"], "evidence_span": "<short quote from '
    'the description, or empty string>"}'
)


def llm_available():
    """Whether an LLM provider is configured in the environment.

    Only checks presence of the key, never reads or logs the value.
    """
    return bool(os.environ.get("ANTHROPIC_API_KEY")) or bool(
        os.environ.get("GEMINI_API_KEY")
    )


def _build_item_text(items):
    lines = []
    for item in items or []:
        name = item.get("name", "")
        description = item.get("description", "")
        declared_category = item.get("category", "")
        line = f"name: {name!r}; declared_category: {declared_category!r}"
        if description:
            line += f"; description: {description!r}"
        lines.append(line)
    return "\n".join(lines) if lines else "(no items)"


def _call_anthropic(item_text):
    api_key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps(
        {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 300,
            "system": _SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": item_text}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=body,
        method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["content"][0]["text"]


def _call_gemini(item_text):
    api_key = os.environ["GEMINI_API_KEY"]
    body = json.dumps(
        {
            "contents": [
                {"parts": [{"text": _SYSTEM_PROMPT + "\n\n" + item_text}]}
            ]
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{GEMINI_URL}?key={api_key}",
        data=body,
        method="POST",
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["candidates"][0]["content"]["parts"][0]["text"]


def _get_llm_raw_response(item_text):
    """Call whichever provider is configured and return the raw text response.

    Separated from classify_items so tests can mock this single seam instead
    of touching the network.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _call_anthropic(item_text)
    if os.environ.get("GEMINI_API_KEY"):
        return _call_gemini(item_text)
    raise RuntimeError("no LLM provider configured")


def _parse_semantic_response(raw_text):
    text = raw_text.strip()
    # Tolerate a fenced code block in case the model wraps its JSON.
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    data = json.loads(text)

    category = data.get("category")
    if category not in SEMANTIC_CATEGORIES:
        raise ValueError(f"unexpected category: {category!r}")

    mismatch = data.get("mismatch")
    if mismatch is not None and mismatch not in policy.MISMATCH_TO_CHECK:
        raise ValueError(f"unexpected mismatch code: {mismatch!r}")

    return {
        "category": category,
        "confidence": float(data.get("confidence", 0.0)),
        "mismatch": mismatch,
        "evidence_span": data.get("evidence_span", "") or "",
    }


def classify_items(items):
    """Classify a list of order items via the LLM into a single semantic verdict.

    Raises on any failure (no provider configured, network error, malformed
    response) — callers that want the FR-8 degrade-gracefully behaviour
    should use run(), which catches these.
    """
    item_text = _build_item_text(items)
    raw = _get_llm_raw_response(item_text)
    return _parse_semantic_response(raw)


def match_fraud_patterns(order):
    """Table-driven fraud pattern match. No LLM involved — always returns.

    fraud_warnings: assessable patterns (policy.assessable_patterns()) whose
      API-visible signal is present in this order.
    unassessable_patterns: the patterns PayPal documents but that this API
      surface cannot evaluate (policy.unassessable_patterns()), always
      returned in full regardless of this specific order.
    """
    order = order or {}
    purchase_units = order.get("purchase_units") or [{}]
    pu = purchase_units[0] if purchase_units else {}
    shipping = pu.get("shipping")
    captures = (pu.get("payments") or {}).get("captures") or []
    capture_status = captures[0].get("status") if captures else None
    amount_value = _safe_float((pu.get("amount") or {}).get("value"))

    fraud_warnings = []
    for pattern in policy.assessable_patterns():
        name = pattern["name"]
        matched = False
        if name == "NO_SHIPPING_ADDRESS_ON_FILE":
            matched = (not shipping) and capture_status == "COMPLETED"
        elif name == "HIGH_VALUE_NO_SIGNATURE":
            matched = (
                amount_value is not None
                and amount_value >= policy.HIGH_VALUE_SIGNATURE_THRESHOLD_USD
            )
        if matched:
            fraud_warnings.append(
                {"name": name, "signal_basis": pattern["signal_basis"]}
            )

    unassessable_patterns = [
        {"name": p["name"], "reason": p["signal_basis"]}
        for p in policy.unassessable_patterns()
    ]

    return {
        "fraud_warnings": fraud_warnings,
        "unassessable_patterns": unassessable_patterns,
    }


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def run(order):
    """Integrate semantic classification + fraud pattern matching.

    Never raises: any semantic-layer failure degrades to ran=False,
    semantic=None while fraud results (table-driven, LLM-independent) are
    still returned (design doc FR-8).
    """
    try:
        fraud = match_fraud_patterns(order)
    except Exception:
        fraud = {"fraud_warnings": [], "unassessable_patterns": []}

    semantic = None
    ran = False
    if llm_available():
        try:
            purchase_units = (order or {}).get("purchase_units") or [{}]
            pu = purchase_units[0] if purchase_units else {}
            items = pu.get("items", [])
            semantic = classify_items(items)
            ran = True
        except Exception:
            semantic = None
            ran = False

    return {
        "ran": ran,
        "semantic": semantic,
        "fraud_warnings": fraud["fraud_warnings"],
        "unassessable_patterns": fraud["unassessable_patterns"],
    }

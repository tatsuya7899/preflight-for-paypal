// content.js — extract transaction/order/capture IDs from the PayPal console
// order-detail screen.
//
// Design source: SPEC-preflight-checker_design.md
//   - "検討した代替案と却下理由": "注文ID同定をDOM自動抽出のみに依存" is rejected
//     — manual input must always be available (demo reproducibility).
//   - "非機能": failure mode (4) "注文ID同定失敗→手動入力フィールドを常時用意".
//
// IMPORTANT: the actual PayPal console DOM has not been inspected yet (see
// SPEC design doc footer "先頭検証タスク"). None of the selectors/patterns
// below are confirmed to match real markup. They are written as a layered
// best-effort guess, ordered from most to least confident, and the caller
// MUST treat anything below 'high' confidence as a suggestion only — never
// as ground truth. The 'none' case (and the panel's manual-input fallback)
// is the only case we can currently guarantee works.

// Candidate URL path patterns that *might* carry a transaction/capture id in
// PayPal's web console. Unverified; extend/replace once real URLs are seen.
const URL_ID_PATTERNS = [
  /\/activity\/payment\/([A-Z0-9]{13,20})/i,
  /\/activities\/transactions\/([A-Z0-9]{13,20})/i,
  /\/activities\/details\/([A-Z0-9]{13,20})/i,
  /[?&](?:transaction_id|txn_id|capture_id|order_id)=([A-Z0-9]{13,20})/i,
];

// data-* attribute names that *might* hold the id on the order detail page.
// Unverified; this is a total-candidate scan, not a confirmed selector.
const DATA_ATTR_CANDIDATES = [
  "data-transaction-id",
  "data-txn-id",
  "data-capture-id",
  "data-order-id",
  "data-testid",
];

// PayPal transaction/capture ids are observed (sandbox fixtures) as 17-char
// uppercase alphanumeric tokens. This is a loose heuristic for free-text
// scanning, not a guarantee — many unrelated tokens can match this shape.
const ID_TEXT_PATTERN = /\b[A-Z0-9]{17}\b/g;

function tryUrlPatterns() {
  const href = window.location.href;
  for (const pattern of URL_ID_PATTERNS) {
    const match = href.match(pattern);
    if (match && match[1]) {
      return { id: match[1], confidence: "candidate", source: "url_pattern" };
    }
  }
  return null;
}

function tryDataAttributes() {
  for (const attr of DATA_ATTR_CANDIDATES) {
    const el = document.querySelector(`[${attr}]`);
    if (el) {
      const value = el.getAttribute(attr);
      if (value && /^[A-Z0-9]{13,20}$/i.test(value)) {
        return { id: value, confidence: "candidate", source: `attribute:${attr}` };
      }
    }
  }
  return null;
}

function tryTextScan() {
  // Scan visible text for id-shaped tokens. Confidence is deliberately low:
  // this cannot distinguish a transaction id from an unrelated token of the
  // same shape (e.g. a tracking number or reference code).
  const text = document.body ? document.body.innerText || "" : "";
  const matches = text.match(ID_TEXT_PATTERN);
  if (matches && matches.length) {
    const unique = Array.from(new Set(matches));
    return unique.map((id) => ({ id, confidence: "candidate", source: "text_scan" }));
  }
  return null;
}

/**
 * Attempt to extract a PayPal order/capture id from the current page.
 *
 * Returns:
 *   { capture_id?, order_id?, confidence: 'high'|'candidate'|'none', candidates?: [...] }
 *
 * There is currently no verified path to 'high' confidence because the real
 * PayPal console DOM has not been inspected (see module header). All
 * resolved candidates are reported under 'candidate' so the panel UI can
 * present them as suggestions next to a manual-input field, never as a
 * silently-applied value.
 */
function extractOrderId() {
  const fromUrl = tryUrlPatterns();
  if (fromUrl) {
    return {
      capture_id: fromUrl.id,
      confidence: fromUrl.confidence,
      candidates: [fromUrl],
    };
  }

  const fromAttr = tryDataAttributes();
  if (fromAttr) {
    return {
      capture_id: fromAttr.id,
      confidence: fromAttr.confidence,
      candidates: [fromAttr],
    };
  }

  const fromText = tryTextScan();
  if (fromText && fromText.length) {
    return {
      confidence: "candidate",
      candidates: fromText,
    };
  }

  return { confidence: "none" };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.type === "extract") {
    try {
      sendResponse(extractOrderId());
    } catch (err) {
      sendResponse({ confidence: "none", error: String(err) });
    }
    return true;
  }
  return false;
});

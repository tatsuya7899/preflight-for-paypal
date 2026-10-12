#!/usr/bin/env python3
"""S4 probe round 2 — can a second dispute be created at all?

1. Check whether an order detail exposes the buyer-side transaction id.
2. Try dispute create on the fresh card capture (3KA63732H29383712) and on
   the order id, with both seller_/buyer_transaction_id fields.
"""
import base64
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"
CARD_CAPTURE = "3KA63732H29383712"   # just created, undisputed
CARD_ORDER = "52U286559X851562A"
WALLET_ORDER_A = "9UD21336FX976210L"  # physical+addr wallet order (capture A)
DISPUTED_ORDER = "3UJ2460633408874H"  # the disputed one — for reference

vals = {}
_LEGACY_ENV = Path.home() / ".config" / "studio" / "paypal-sandbox.env"
_ENV = _LEGACY_ENV if _LEGACY_ENV.exists() else \
    Path.home() / ".config" / "preflight" / "paypal-sandbox.env"
for line in _ENV.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip("'\"")

basic = base64.b64encode(
    f"{vals['PAYPAL_CLIENT_ID']}:{vals['PAYPAL_CLIENT_SECRET']}".encode()).decode()


def api(method, path, token=None, basic_auth=None, payload=None):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    req.add_header("Authorization",
                   "Basic " + basic_auth if basic_auth else "Bearer " + token)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return {"_ok": True, "_status": r.status,
                    "data": json.loads(body) if body else {}}
    except urllib.error.HTTPError as e:
        return {"_ok": False, "_status": e.code, "_body": e.read().decode()[:900]}


tok = api("POST", "/v1/oauth2/token", basic_auth=basic,
          payload=b"grant_type=client_credentials")
token = tok["data"]["access_token"]
print("TOKEN OK\n")

# 1. order detail — does it expose buyer-side ids?
for label, oid in [("card_order", CARD_ORDER), ("disputed_wallet_order", DISPUTED_ORDER)]:
    print(f"== order detail: {label} {oid} ==")
    det = api("GET", f"/v2/checkout/orders/{oid}", token=token)
    if det.get("_ok"):
        d = det["data"]
        pu = (d.get("purchase_units") or [{}])[0]
        pays = pu.get("payments", {})
        print(f"  status={d.get('status')} payer={json.dumps(d.get('payer', {}), ensure_ascii=False)[:200]}")
        for cap in pays.get("captures", []):
            print(f"  capture id={cap.get('id')} keys={sorted(cap.keys())}")
    else:
        print(f"  GET failed {det.get('_status')}")

# 2. dispute create variants on fresh captures
targets = [
    ("card_capture/seller_field", CARD_CAPTURE, "seller_transaction_id"),
    ("card_capture/buyer_field", CARD_CAPTURE, "buyer_transaction_id"),
    ("card_order_as_txn/buyer", CARD_ORDER, "buyer_transaction_id"),
]
for label, txn_id, field in targets:
    print(f"\n-- create attempt: {label} ({field}={txn_id}) --")
    payload = {
        "disputed_transactions": [{field: txn_id}],
        "reason": "UNAUTHORISED",
        "dispute_amount": {"currency_code": "USD", "value": "10.00"},
    }
    d = api("POST", "/v1/customer/disputes", token=token,
            payload=json.dumps(payload).encode())
    print(f"create: _ok={d.get('_ok')} status={d.get('_status')}")
    body = d.get("data") or d.get("_body", "")
    print(json.dumps(body, ensure_ascii=False)[:900])
    if d.get("_ok"):
        print("DISPUTE CREATED:", json.dumps(body, ensure_ascii=False)[:1500])
        break

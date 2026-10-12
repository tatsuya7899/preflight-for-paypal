#!/usr/bin/env python3
"""S3+S4 probe — what can be done server-side in PayPal sandbox.

S3: payment_source variation — can a card-funded capture be produced without
    buyer browser approval (confirm-payment-source), and does
    seller_protection.status differ from a PayPal-wallet capture?
S4: can POST /v1/customer/disputes create an UNAUTHORIZED dispute on an
    existing capture (undisputed: A=4EC24563F7235632E)?

Prints only statuses/field names — never credentials or PII.
"""
import base64
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"
CAPTURE_A = "4EC24563F7235632E"   # physical + address, currently undisputed

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


def api(method, path, token=None, basic_auth=None, payload=None, req_id=None):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    req.add_header("Authorization",
                   "Basic " + basic_auth if basic_auth else "Bearer " + token)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if req_id:
        req.add_header("PayPal-Request-Id", req_id)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return {"_ok": True, "_status": r.status,
                    "data": json.loads(body) if body else {}}
    except urllib.error.HTTPError as e:
        return {"_ok": False, "_status": e.code, "_body": e.read().decode()[:900]}


tok = api("POST", "/v1/oauth2/token", basic_auth=basic,
          payload=b"grant_type=client_credentials")
if not tok.get("_ok"):
    print("token failed:", tok)
    sys.exit(1)
token = tok["data"]["access_token"]
print("TOKEN OK\n")

# ---------- S3: card-funded order without buyer browser approval ----------
print("== S3: order with card payment_source ==")


def luhn_check_digit(prefix):
    digits = [int(c) for c in prefix]
    for i in range(len(digits) - 1, -1, -2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    return str((10 - sum(digits) % 10) % 10)


CARD_NUMBER = "403203676439535" + luhn_check_digit("403203676439535")
order_payload = {
    "intent": "CAPTURE",
    "purchase_units": [{
        "amount": {"currency_code": "USD", "value": "10.00",
                   "breakdown": {"item_total": {"currency_code": "USD", "value": "10.00"}}},
        "items": [{"name": "Widget (card test)", "quantity": "1",
                   "unit_amount": {"currency_code": "USD", "value": "10.00"},
                   "category": "PHYSICAL_GOODS"}],
        "shipping": {"name": {"full_name": "Sandbox Buyer"},
                     "address": {"address_line_1": "1 Main St",
                                 "admin_area_2": "San Jose", "admin_area_1": "CA",
                                 "postal_code": "95131", "country_code": "US"}},
    }],
    "payment_source": {
        "card": {
            "number": CARD_NUMBER,
            "expiry": "2030-01",
            "security_code": "123",
            "name": "Sandbox Buyer",
            "billing_address": {
                "address_line_1": "1 Main St", "admin_area_2": "San Jose",
                "admin_area_1": "CA", "postal_code": "95131", "country_code": "US"},
        }
    },
}
import uuid
o = api("POST", "/v2/checkout/orders", token=token,
        payload=json.dumps(order_payload).encode(), req_id=str(uuid.uuid4()))
if o.get("_ok"):
    oid = o["data"]["id"]
    print(f"order created: {oid} status={o['data'].get('status')}")
    # With card payment_source inline, the order may already be COMPLETED.
    det = api("GET", f"/v2/checkout/orders/{oid}", token=token)
    if det.get("_ok"):
        try:
            cap0 = det["data"]["purchase_units"][0]["payments"]["captures"][0]
            print(f"captured id: {cap0.get('id')} status={cap0.get('status')}")
            print(f"  seller_protection: {json.dumps(cap0.get('seller_protection'), ensure_ascii=False)}")
            print(f"  payment_source: {json.dumps(det['data'].get('payment_source', {}), ensure_ascii=False)[:300]}")
        except (KeyError, IndexError) as e:
            print(f"no capture in order detail: {e}")
            print(json.dumps(det["data"], ensure_ascii=False)[:800])
    else:
        print(f"order GET failed: {det.get('_status')} {det.get('_body','')[:300]}")
    if det.get("_ok") and det["data"].get("status") != "COMPLETED":
        c = api("POST", f"/v2/checkout/orders/{oid}/confirm-payment-source", token=token,
                payload=json.dumps(order_payload["payment_source"]).encode())
        print(f"confirm-payment-source: _ok={c.get('_ok')} status={c.get('_status')} "
              f"order_status={(c.get('data') or {}).get('status') if c.get('_ok') else c.get('_body', '')[:200]}")
        if c.get("_ok"):
            cap = api("POST", f"/v2/checkout/orders/{oid}/capture", token=token, payload=b"{}")
            if cap.get("_ok"):
                try:
                    cap0 = cap["data"]["purchase_units"][0]["payments"]["captures"][0]
                    print(f"capture: {cap0.get('id')} status={cap['data'].get('status')}")
                    print(f"  seller_protection: {json.dumps(cap0.get('seller_protection'), ensure_ascii=False)}")
                except (KeyError, IndexError):
                    print("no capture after confirm")
            else:
                print(f"capture failed: {cap.get('_status')} {cap.get('_body','')[:300]}")
else:
    print(f"order create failed: {o.get('_status')} {o.get('_body','')[:300]}")

# ---------- S4: create UNAUTHORIZED dispute via API ----------
print("\n== S4: POST /v1/customer/disputes (create UNAUTHORIZED) ==")
# Try field variants: buyer_transaction_id field name, then seller variant
attempts = [
    ("MERCH-buyer_field", "MERCHANDISE_OR_SERVICE_NOT_RECEIVED",
     {"buyer_transaction_id": CAPTURE_A}),
    ("UNAUTH-buyer_field", "UNAUTHORISED",
     {"buyer_transaction_id": CAPTURE_A}),
]
for label, reason, txn in attempts:
    print(f"\n-- attempt {label} --")
    create_payload = {
        "disputed_transactions": [txn],
        "reason": reason,
        "dispute_amount": {"currency_code": "USD", "value": "10.00"},
    }
    d = api("POST", "/v1/customer/disputes", token=token,
            payload=json.dumps(create_payload).encode())
    print(f"create: _ok={d.get('_ok')} status={d.get('_status')}")
    print(json.dumps(d.get("data") or d.get("_body", ""), ensure_ascii=False)[:900])
    if d.get("_ok"):
        break

print("\n== S4b: list disputes (what exists) ==")
lst = api("GET", "/v1/customer/disputes?page_size=20", token=token)
if lst.get("_ok"):
    items = (lst["data"].get("items") or [])
    for it in items:
        print(f"  {it.get('dispute_id')} reason={it.get('reason')} status={it.get('status')}")
else:
    print(f"list failed: {lst.get('_status')} {lst.get('_body','')[:300]}")

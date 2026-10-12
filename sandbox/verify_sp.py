#!/usr/bin/env python3
"""PayPal sandbox: verify whether capture responses return seller_protection.status.

Gate-0 condition 1 for SP-1 (seller-protection-checker):
  Does capture actually return NOT_ELIGIBLE for DIGITAL_GOODS / missing-address orders?

Flow: token -> create 3 orders -> user approves each in browser (sandbox buyer)
      -> poll until APPROVED -> capture -> print seller_protection.status.

Credentials: read from ~/.config/preflight/paypal-sandbox.env (never printed;
legacy ~/.config/studio/ path still honored when it exists).
Buyer approval needs a sandbox *personal* account login
(Developer Dashboard -> Testing Tools -> Sandbox Accounts -> personal account password).
"""
import base64
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"
_LEGACY_ENV = Path.home() / ".config" / "studio" / "paypal-sandbox.env"
ENV_FILE = _LEGACY_ENV if _LEGACY_ENV.exists() else \
    Path.home() / ".config" / "preflight" / "paypal-sandbox.env"


def load_env(path):
    vals = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip("'").strip('"')
    return vals


def api(method, path, token=None, basic=None, payload=None):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    if basic:
        req.add_header("Authorization", "Basic " + basic)
    elif token:
        req.add_header("Authorization", "Bearer " + token)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} on {method} {path}: {e.read().decode()[:800]}")
        sys.exit(1)


CASES = {
    "A_control_physical_with_addr": {
        "items": [{"name": "Test Widget", "quantity": "1",
                   "unit_amount": {"currency_code": "USD", "value": "10.00"},
                   "category": "PHYSICAL_GOODS"}],
        "shipping": {"name": {"full_name": "Sandbox Buyer"},
                     "address": {"address_line_1": "1 Main St",
                                 "admin_area_2": "San Jose",
                                 "admin_area_1": "CA", "postal_code": "95131",
                                 "country_code": "US"}},
    },
    "B_digital_goods": {
        "items": [{"name": "Digital License", "quantity": "1",
                   "unit_amount": {"currency_code": "USD", "value": "10.00"},
                   "category": "DIGITAL_GOODS"}],
    },
    "C_physical_no_shipping": {
        "items": [{"name": "Physical No Addr", "quantity": "1",
                   "unit_amount": {"currency_code": "USD", "value": "10.00"},
                   "category": "PHYSICAL_GOODS"}],
    },
}


def build_order(case):
    items = case["items"]
    total = sum(float(i["unit_amount"]["value"]) * int(i["quantity"]) for i in items)
    pu = {
        "amount": {"currency_code": "USD", "value": f"{total:.2f}",
                   "breakdown": {"item_total": {"currency_code": "USD",
                                                "value": f"{total:.2f}"}}},
        "items": items,
    }
    if "shipping" in case:
        pu["shipping"] = case["shipping"]
    return {"intent": "CAPTURE", "purchase_units": [pu]}


def main():
    env = load_env(ENV_FILE)
    missing = [k for k in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET") if k not in env]
    if missing:
        print(f"env keys missing: {missing} (file has: {sorted(env)})")
        sys.exit(1)
    cid, sec = env["PAYPAL_CLIENT_ID"], env["PAYPAL_CLIENT_SECRET"]
    print(f"cred lens: client_id={len(cid)} secret={len(sec)}")
    basic = base64.b64encode(f"{cid}:{sec}".encode()).decode()
    token = api("POST", "/v1/oauth2/token", basic=basic,
                payload=b"grant_type=client_credentials")["access_token"]
    print("TOKEN OK")

    orders = {}
    for name, case in CASES.items():
        o = api("POST", "/v2/checkout/orders", token=token,
                payload=json.dumps(build_order(case)).encode())
        oid = o["id"]
        approve = next(l["href"] for l in o["links"] if l["rel"] in ("approve", "payer-action"))
        orders[name] = {"id": oid, "approve": approve}
        print(f"\n[{name}] created {oid}\n  approve: {approve}")

    print("\n>>> 上記3つのapproveリンクをブラウザで開き、sandbox個人アカウントで全て承認してください。")
    print(">>> 承認をポーリングします(最長10分)...")

    deadline = time.time() + 600
    pending = set(orders)
    while pending and time.time() < deadline:
        time.sleep(5)
        for name in list(pending):
            st = api("GET", f"/v2/checkout/orders/{orders[name]['id']}", token=token)
            status = st.get("status")
            if status == "APPROVED":
                print(f"[{name}] APPROVED")
                pending.discard(name)
            elif status in ("VOIDED", "COMPLETED"):
                print(f"[{name}] unexpected {status}")
                pending.discard(name)
    if pending:
        print(f"timeout waiting: {pending}")
        sys.exit(1)

    print("\n== capture results ==")
    results = {}
    for name, o in orders.items():
        cap = api("POST", f"/v2/checkout/orders/{o['id']}/capture", token=token,
                  payload=b"{}")
        try:
            sp = cap["purchase_units"][0]["payments"]["captures"][0]["seller_protection"]
        except (KeyError, IndexError):
            sp = None
        results[name] = sp
        print(f"\n[{name}]")
        print(f"  order status: {cap.get('status')}")
        print(f"  seller_protection: {json.dumps(sp, ensure_ascii=False)}")

    print("\n== verdict ==")
    for name, sp in results.items():
        print(f"  {name}: {sp['status'] if sp else 'FIELD ABSENT'}")


if __name__ == "__main__":
    main()

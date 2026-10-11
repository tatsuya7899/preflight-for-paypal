#!/usr/bin/env python3
"""Batch 2: variants designed to flip seller_protection.status if sandbox computes it."""
import base64
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"
ENV_FILE = Path.home() / ".config" / "studio" / "paypal-sandbox.env"

vals = {}
for line in ENV_FILE.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip("'\"")

basic = base64.b64encode(
    f"{vals['PAYPAL_CLIENT_ID']}:{vals['PAYPAL_CLIENT_SECRET']}".encode()
).decode()


def api(method, path, token=None, basic=None, payload=None):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    req.add_header("Authorization", "Basic " + basic if basic else "Bearer " + token)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} on {method} {path}: {e.read().decode()[:600]}")
        sys.exit(1)


ADDR = {"name": {"full_name": "Sandbox Buyer"},
        "address": {"address_line_1": "1 Main St", "admin_area_2": "San Jose",
                    "admin_area_1": "CA", "postal_code": "95131", "country_code": "US"}}


def item(name, value, cat):
    return {"name": name, "quantity": "1",
            "unit_amount": {"currency_code": "USD", "value": value},
            "category": cat}


def order(items=None, shipping=None, amount="10.00", ctx=None):
    pu = {"amount": {"currency_code": "USD", "value": amount}}
    if items:
        pu["items"] = items
        pu["amount"]["breakdown"] = {"item_total": {"currency_code": "USD",
                                                    "value": amount}}
    if shipping:
        pu["shipping"] = shipping
    o = {"intent": "CAPTURE", "purchase_units": [pu]}
    if ctx:
        o["payment_source"] = {"paypal": {"experience_context": ctx}}
    return o


CASES = {
    "D_highvalue_800": order([item("Expensive Widget", "800.00", "PHYSICAL_GOODS")],
                             shipping=ADDR, amount="800.00"),
    "E_no_items_amount_only": order(amount="10.00"),
    "F_no_shipping_pref": order([item("Widget", "10.00", "PHYSICAL_GOODS")],
                                ctx={"shipping_preference": "NO_SHIPPING"}),
}

token = api("POST", "/v1/oauth2/token", basic=basic,
            payload=b"grant_type=client_credentials")["access_token"]
print("TOKEN OK")

for name, payload in CASES.items():
    o = api("POST", "/v2/checkout/orders", token=token,
            payload=json.dumps(payload).encode())
    link = next(l["href"] for l in o["links"] if l["rel"] in ("approve", "payer-action"))
    print(f"[{name}] {o['id']}\n  approve: {link}")

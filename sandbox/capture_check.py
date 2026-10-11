#!/usr/bin/env python3
"""Capture approved orders and print seller_protection. Reusable for B/C."""
import base64
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"
IDS = {
    "A_control_physical_with_addr": "2YD26664U8090205J",
    "B_digital_goods": "36Y12192ND5364537",
    "C_physical_no_shipping": "1E363983N42578105",
    "D_highvalue_800": "56C46835SC281864L",
    "E_no_items_amount_only": "83V50724122773147",
    "F_no_shipping_pref": "3UJ2460633408874H",
}
targets = sys.argv[1:] or list(IDS)

vals = {}
for line in (Path.home() / ".config" / "studio" / "paypal-sandbox.env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip("'\"")

basic = base64.b64encode(
    f"{vals['PAYPAL_CLIENT_ID']}:{vals['PAYPAL_CLIENT_SECRET']}".encode()
).decode()

req = urllib.request.Request(BASE + "/v1/oauth2/token",
                             data=b"grant_type=client_credentials")
req.add_header("Authorization", "Basic " + basic)
token = json.loads(urllib.request.urlopen(req).read())["access_token"]

for name in targets:
    oid = IDS[name]
    req = urllib.request.Request(BASE + f"/v2/checkout/orders/{oid}/capture",
                                 data=b"{}", method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        cap = json.loads(urllib.request.urlopen(req).read())
        cap0 = cap["purchase_units"][0]["payments"]["captures"][0]
        sp = cap0.get("seller_protection")
        print(f"[{name}] order_status={cap.get('status')} capture_id={cap0.get('id')}")
        print(f"  seller_protection: {json.dumps(sp, ensure_ascii=False)}")
    except urllib.error.HTTPError as e:
        print(f"[{name}] capture HTTP {e.code}: {e.read().decode()[:400]}")

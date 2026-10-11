#!/usr/bin/env python3
"""Check current status of the 3 test orders."""
import base64
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"
IDS = {
    "A_control_physical_with_addr": "2YD26664U8090205J",
    "B_digital_goods": "36Y12192ND5364537",
    "C_physical_no_shipping": "1E363983N42578105",
}

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

for name, oid in IDS.items():
    req = urllib.request.Request(BASE + f"/v2/checkout/orders/{oid}")
    req.add_header("Authorization", "Bearer " + token)
    try:
        o = json.loads(urllib.request.urlopen(req).read())
        payer = o.get("payer", {})
        print(f"{name}: status={o.get('status')} "
              f"payer_email={payer.get('email_address', '-')}")
    except urllib.error.HTTPError as e:
        print(f"{name}: HTTP {e.code} {e.read().decode()[:200]}")

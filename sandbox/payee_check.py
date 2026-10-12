#!/usr/bin/env python3
"""Check who received order A's payment — is it the app's sandbox business account?"""
import base64
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE = "https://api-m.sandbox.paypal.com"

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
    f"{vals['PAYPAL_CLIENT_ID']}:{vals['PAYPAL_CLIENT_SECRET']}".encode()
).decode()

req = urllib.request.Request(BASE + "/v1/oauth2/token",
                             data=b"grant_type=client_credentials")
req.add_header("Authorization", "Basic " + basic)
token = json.loads(urllib.request.urlopen(req).read())["access_token"]

for oid in ["2YD26664U8090205J", "36Y12192ND5364537"]:
    req = urllib.request.Request(BASE + f"/v2/checkout/orders/{oid}")
    req.add_header("Authorization", "Bearer " + token)
    o = json.loads(urllib.request.urlopen(req).read())
    pu = o["purchase_units"][0]
    print(f"order {oid}: payee={json.dumps(pu.get('payee'), ensure_ascii=False)}")
    try:
        cap = pu["payments"]["captures"][0]
        print(f"  capture_id={cap['id']} final={cap.get('final_capture')}")
    except (KeyError, IndexError):
        pass

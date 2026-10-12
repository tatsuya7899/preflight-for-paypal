#!/usr/bin/env python3
"""Diagnose which environment the stored PayPal credentials belong to.
Tries oauth token on both sandbox and live endpoints. Prints only OK/HTTP status."""
import base64
import json
import urllib.request
import urllib.error
from pathlib import Path

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

for label, base in [("sandbox", "https://api-m.sandbox.paypal.com"),
                    ("live", "https://api-m.paypal.com")]:
    req = urllib.request.Request(base + "/v1/oauth2/token",
                                 data=b"grant_type=client_credentials")
    req.add_header("Authorization", "Basic " + basic)
    try:
        with urllib.request.urlopen(req) as r:
            print(f"{label}: AUTH OK")
    except urllib.error.HTTPError as e:
        print(f"{label}: HTTP {e.code} {e.read().decode()[:120]}")

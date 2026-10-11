#!/usr/bin/env python3
"""Shipment tracking write test — is tracker registration real or stubbed?"""
import base64, json, os, ssl, urllib.request, urllib.parse

BASE = "https://api-m.sandbox.paypal.com"
CTX = ssl.create_default_context()

creds = {}
for ln in open(os.path.expanduser("~/.config/studio/paypal-sandbox.env")):
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.strip().split("=", 1)
        creds[k.strip()] = v.strip().strip("'\"")

def api(method, path, token=None, payload=None):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:1200]}

tk = base64.b64encode(f"{creds['PAYPAL_CLIENT_ID']}:{creds['PAYPAL_CLIENT_SECRET']}".encode()).decode()
req = urllib.request.Request(BASE + "/v1/oauth2/token",
                             data=b"grant_type=client_credentials",
                             headers={"Authorization": f"Basic {tk}",
                                      "Content-Type": "application/x-www-form-urlencoded"})
tok = json.loads(urllib.request.urlopen(req, context=CTX).read())["access_token"]
print("TOKEN OK")

TXNS = {
    "A_physical": "4EC24563F7235632E",
    "F_no_shipping_disputed": "3J366679AY2283450",
}

for label, txn in TXNS.items():
    print(f"\n===== {label} ({txn}) =====")
    body = {
        "trackers": [{
            "transaction_id": txn,
            "tracking_number": "1Z999AA10123456784",
            "status": "SHIPPED",
            "carrier": "UPS",
        }],
        "tracking_number_type": "CARRIER_PROVIDED",
    }
    r = api("POST", "/v1/shipping/trackers-batch", token=tok,
            payload=json.dumps(body).encode())
    print("POST trackers-batch:", json.dumps(r, ensure_ascii=False, indent=1)[:1800])

    print("\nGET trackers:")
    q = api("GET", f"/v1/shipping/trackers?transaction_id={txn}", token=tok)
    print(json.dumps(q, ensure_ascii=False, indent=1)[:1800])

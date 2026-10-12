#!/usr/bin/env python3
"""Fetch real capture + dispute responses and save as test fixtures."""
import base64, json, os, ssl, urllib.request

BASE = "https://api-m.sandbox.paypal.com"
CTX = ssl.create_default_context()
OUT = os.path.join(os.path.dirname(__file__), "..", "backend", "fixtures")
os.makedirs(OUT, exist_ok=True)

creds = {}
_LEGACY_ENV = os.path.expanduser("~/.config/studio/paypal-sandbox.env")
_ENV = _LEGACY_ENV if os.path.exists(_LEGACY_ENV) else \
    os.path.expanduser("~/.config/preflight/paypal-sandbox.env")
for ln in open(_ENV):
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
        return {"_http_error": e.code, "_body": e.read().decode()[:600]}

tk = base64.b64encode(f"{creds['PAYPAL_CLIENT_ID']}:{creds['PAYPAL_CLIENT_SECRET']}".encode()).decode()
req = urllib.request.Request(BASE + "/v1/oauth2/token",
                             data=b"grant_type=client_credentials",
                             headers={"Authorization": f"Basic {tk}",
                                      "Content-Type": "application/x-www-form-urlencoded"})
tok = json.loads(urllib.request.urlopen(req, context=CTX).read())["access_token"]
print("TOKEN OK")

CAPTURES = {
    "A_physical_with_addr": "4EC24563F7235632E",
    "B_digital_goods": "13E67607MS6117934",
    "C_physical_no_addr": "2B190886TP583404W",
    "D_highvalue_800": "76X32521BG861322V",
    "E_no_items": "8R484715XN459481P",
    "F_no_shipping_disputed": "3J366679AY2283450",
}

for name, cid in CAPTURES.items():
    r = api("GET", f"/v2/payments/captures/{cid}", token=tok)
    fn = os.path.join(OUT, f"capture_{name}.json")
    with open(fn, "w") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print(f"saved {fn} status={r.get('status', r.get('_http_error'))}")

# Also fetch the orders for full context
ORDERS = {
    "A": "2YD26664U8090205J", "B": "36Y12192ND5364537", "C": "1E363983N42578105",
    "D": "56C46835SC281864L", "E": "83V50724122773147", "F": "3UJ2460633408874H",
}
for name, oid in ORDERS.items():
    r = api("GET", f"/v2/checkout/orders/{oid}", token=tok)
    fn = os.path.join(OUT, f"order_{name}.json")
    with open(fn, "w") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print(f"saved {fn} status={r.get('status', r.get('_http_error'))}")

d = api("GET", "/v1/customer/disputes/PP-R-XGB-10190971", token=tok)
fn = os.path.join(OUT, "dispute_PP-R-XGB-10190971.json")
with open(fn, "w") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
print(f"saved {fn} status={d.get('status')} life={d.get('dispute_life_cycle_stage')}")

#!/usr/bin/env python3
"""Final dispute resolution attempt: supporting info -> adjudicate or accept-claim."""
import base64, json, os, ssl, time, urllib.request

BASE = "https://api-m.sandbox.paypal.com"
CTX = ssl.create_default_context()
DID = "PP-R-XGB-10190971"

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

def rels():
    d = api("GET", f"/v1/customer/disputes/{DID}", token=tok)
    return d, [l["rel"] for l in d.get("links", [])]

d, links = rels()
print(f"start: status={d.get('status')} life={d.get('dispute_life_cycle_stage')} links={links}")

# provide-supporting-info
r = api("POST", f"/v1/customer/disputes/{DID}/provide-supporting-info", token=tok,
        payload=json.dumps({"notes": "additional info: no shipment was made"}).encode())
print("provide-supporting-info:", json.dumps(r, ensure_ascii=False)[:500])

for i in range(6):
    time.sleep(10)
    d, links = rels()
    print(f"  poll{i}: status={d.get('status')} life={d.get('dispute_life_cycle_stage')} links={links}")
    if "adjudicate" in links:
        break

d, links = rels()
if "adjudicate" in links:
    adj = api("POST", f"/v1/customer/disputes/{DID}/adjudicate", token=tok,
              payload=json.dumps({"adjudication_outcome": "BUYER_FAVOR"}).encode())
    print("adjudicate:", json.dumps(adj, ensure_ascii=False)[:800])
elif "accept_claim" in links:
    ac = api("POST", f"/v1/customer/disputes/{DID}/accept-claim", token=tok,
             payload=json.dumps({
                 "note": "seller accepts claim - no proof of shipment",
                 "accept_claim_reason": "DID_NOT_SHIP_ITEM",
                 "accept_claim_type": "REFUND"
             }).encode())
    print("accept-claim:", json.dumps(ac, ensure_ascii=False)[:800])

d, links = rels()
print(f"FINAL: status={d.get('status')} life={d.get('dispute_life_cycle_stage')} "
      f"outcome={json.dumps(d.get('dispute_outcome'))} links={links}")

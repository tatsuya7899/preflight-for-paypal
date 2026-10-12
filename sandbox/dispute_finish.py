#!/usr/bin/env python3
"""Finish dispute lifecycle: provide evidence -> adjudicate."""
import json, os, ssl, time, urllib.request

BASE = "https://api-m.sandbox.paypal.com"
CTX = ssl.create_default_context()

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

creds = {}
_LEGACY_ENV = os.path.expanduser("~/.config/studio/paypal-sandbox.env")
_ENV = _LEGACY_ENV if _LEGACY_ENV.exists() else \
    os.path.expanduser("~/.config/preflight/paypal-sandbox.env")
for ln in open(_ENV):
    if "=" in ln and not ln.startswith("#"):
        k, v = ln.strip().split("=", 1)
        creds[k.strip()] = v.strip().strip("'\"")

import base64
tk = base64.b64encode(f"{creds['PAYPAL_CLIENT_ID']}:{creds['PAYPAL_CLIENT_SECRET']}".encode()).decode()
tok = api("POST", "/v1/oauth2/token", payload=b"grant_type=client_credentials")
# need basic auth for token endpoint
req = urllib.request.Request(BASE + "/v1/oauth2/token",
                             data=b"grant_type=client_credentials",
                             headers={"Authorization": f"Basic {tk}",
                                      "Content-Type": "application/x-www-form-urlencoded"})
tok = json.loads(urllib.request.urlopen(req, context=CTX).read())["access_token"]
print("TOKEN OK")

DID = "PP-R-XGB-10190971"

def show():
    d = api("GET", f"/v1/customer/disputes/{DID}", token=tok)
    print(f"  status={d.get('status')} life={d.get('dispute_life_cycle_stage')} "
          f"links={[l['rel'] for l in d.get('links', [])]}")
    return d

print("== initial ==")
show()

print("== provide-evidence ==")
r = api("POST", f"/v1/customer/disputes/{DID}/provide-evidence", token=tok,
        payload=json.dumps({
            "evidences": [{
                "evidence_type": "PROOF_OF_FULFILLMENT",
                "notes": "sandbox test: tracking not available (NO_SHIPPING order)",
                "evidence_info": {"tracking_info": [{
                    "carrier_name": "UPS",
                    "tracking_number": "1Z999AA10123456784"
                }]}
            }]
        }).encode())
print(json.dumps(r, ensure_ascii=False)[:800])

print("== poll for adjudicate ==")
done = False
for i in range(18):
    d = api("GET", f"/v1/customer/disputes/{DID}", token=tok)
    rels = [l["rel"] for l in d.get("links", [])]
    print(f"  poll{i}: status={d.get('status')} life={d.get('dispute_life_cycle_stage')} links={rels}")
    if "adjudicate" in rels:
        done = True
        break
    if d.get("status") in ("RESOLVED", "SETTLED", "CLOSED"):
        done = True
        break
    time.sleep(10)

if "adjudicate" in [l["rel"] for l in api("GET", f"/v1/customer/disputes/{DID}", token=tok).get("links", [])]:
    print("== adjudicate BUYER_FAVOR ==")
    adj = api("POST", f"/v1/customer/disputes/{DID}/adjudicate", token=tok,
              payload=json.dumps({"adjudication_outcome": "BUYER_FAVOR"}).encode())
    print(json.dumps(adj, ensure_ascii=False)[:800])

print("== final ==")
fin = show()
for k in ("dispute_outcome", "money_movements", "extensions"):
    if k in fin:
        print(f"  {k}:", json.dumps(fin[k], ensure_ascii=False)[:500])

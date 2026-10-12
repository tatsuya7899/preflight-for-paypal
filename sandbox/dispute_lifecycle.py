#!/usr/bin/env python3
"""Disputes sandbox lifecycle: list -> show -> require-evidence -> adjudicate -> settle.

Gate-0 re-verdict condition 1: does the dispute machine actually work in sandbox
and return real evidence_type values from require-evidence?
Seller-side: merchant app creds only (no buyer assertion needed for these calls).
"""
import base64
import json
import sys
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


def api(method, path, token=None, basic=None, payload=None, raw=False):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    req.add_header("Authorization", "Basic " + basic if basic else "Bearer " + token)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()) if not raw else r.read()
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:800]}


token = api("POST", "/v1/oauth2/token", basic=basic,
            payload=b"grant_type=client_credentials")["access_token"]
print("TOKEN OK\n")

# 1. direct GET by case id, then fall back to list
CASE_ID = "PP-R-XGB-10190971"
print(f"== 1. GET /v1/customer/disputes/{CASE_ID} (direct) ==")
direct = api("GET", f"/v1/customer/disputes/{CASE_ID}", token=token)
print(json.dumps(direct, ensure_ascii=False, indent=1)[:2500])

if "_http_error" in direct:
    print("\n== 1b. list fallback ==")
    listing = api("GET", "/v1/customer/disputes?page_size=10", token=token)
    print(json.dumps(listing, ensure_ascii=False, indent=1)[:2000])
    sys.exit(1)

did = CASE_ID
print(f"\nusing dispute_id={did}")

# 2. show dispute details
print("\n== 2. GET dispute detail ==")
det = api("GET", f"/v1/customer/disputes/{did}", token=token)
print(json.dumps(det, ensure_ascii=False, indent=1)[:3000])

# 3. require-evidence (ask seller for evidence) — sandbox-only
print("\n== 3. POST require-evidence (SELLER) ==")
rev = api("POST", f"/v1/customer/disputes/{did}/require-evidence", token=token,
          payload=json.dumps({"action": "SELLER_EVIDENCE"}).encode())
print(json.dumps(rev, ensure_ascii=False, indent=1)[:3000])

# re-show to see requested evidence types
print("\n== 3b. dispute after require-evidence ==")
det2 = api("GET", f"/v1/customer/disputes/{did}", token=token)
print(json.dumps(det2, ensure_ascii=False, indent=1)[:3000])

# 4. provide-evidence (seller submits proof of fulfillment)
print("\n== 4. POST provide-evidence ==")
ev = api("POST", f"/v1/customer/disputes/{did}/provide-evidence", token=token,
         payload=json.dumps({
             "evidences": [{
                 "evidence_type": "PROOF_OF_FULFILLMENT",
                 "notes": "sandbox test evidence",
             }]
         }).encode())
print(json.dumps(ev, ensure_ascii=False, indent=1)[:1500])

# state after evidence
det3 = api("GET", f"/v1/customer/disputes/{did}", token=token)
print(f"state after evidence: status={det3.get('status')} "
      f"life_cycle={det3.get('dispute_life_cycle_stage')} "
      f"links={[l['rel'] for l in det3.get('links', [])]}")

# 5. poll for adjudicate link, then settle (=adjudicate)
import time
print("\n== 5. wait for adjudicate link ==")
ok = False
for i in range(12):
    d = api("GET", f"/v1/customer/disputes/{did}", token=token)
    rels = [l["rel"] for l in d.get("links", [])]
    print(f"  poll{i}: status={d.get('status')} life={d.get('dispute_life_cycle_stage')} links={rels}")
    if "adjudicate" in rels:
        ok = True
        break
    time.sleep(10)
if not ok:
    print("adjudicate link never appeared")
else:
    adj = api("POST", f"/v1/customer/disputes/{did}/adjudicate", token=token,
              payload=json.dumps({"adjudication_outcome": "BUYER_FAVOR"}).encode())
    print("adjudicate:", json.dumps(adj, ensure_ascii=False)[:800])

# final state
print("\n== final state ==")
fin = api("GET", f"/v1/customer/disputes/{did}", token=token)
print(f"status={fin.get('status')} life_cycle={fin.get('dispute_life_cycle_stage')} "
      f"outcome={fin.get('dispute_outcome', {})}")

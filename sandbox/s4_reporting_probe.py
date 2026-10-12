import base64, json, urllib.request, urllib.error
from pathlib import Path
BASE = "https://api-m.sandbox.paypal.com"
vals = {}
for line in (Path.home() / ".config/studio/paypal-sandbox.env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip("'\"")
basic = base64.b64encode(f"{vals['PAYPAL_CLIENT_ID']}:{vals['PAYPAL_CLIENT_SECRET']}".encode()).decode()

def api(method, path, token=None, basic_auth=None, payload=None):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    req.add_header("Authorization", "Basic " + basic_auth if basic_auth else "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {"_ok": True, "data": json.loads(r.read() or b"{}")}
    except urllib.error.HTTPError as e:
        return {"_ok": False, "_status": e.code, "_body": e.read().decode()[:600]}

tk = api("POST", "/v1/oauth2/token", basic_auth=basic, payload=b"grant_type=client_credentials")
tok = tk["data"]["access_token"]
for txn in ("3KA63732H29383712", "4EC24563F7235632E"):
    r = api("GET", f"/v1/reporting/transactions?transaction_id={txn}", token=tok)
    print(f"== {txn} ==")
    print(json.dumps(r.get("data") or r, ensure_ascii=False)[:2000])

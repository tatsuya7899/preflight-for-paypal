"""PayPal sandbox API client — stdlib only (urllib/ssl/json), no third-party deps.

Design source: SPEC-preflight-checker_design.md
- "触るファイル": backend/paypal.py — OAuth・Orders取得・trackers-batch POST/trackers GET
  (既存sandbox/*.pyのロジック移植)
- "ID契約(P0-1)": capture_id/order_id相互解決
- 非機能: client_secret等はレスポンス・ログに出さない。HTTPエラーは例外でなくdictで返す。

Auth/HTTP shape copied from sandbox/tracking_test.py and sandbox/dispute_lifecycle.py.
"""
import base64
import json
import os
import ssl
import urllib.error
import urllib.request

BASE = "https://api-m.sandbox.paypal.com"
ENV_PATH = os.path.expanduser("~/.config/studio/paypal-sandbox.env")
_CTX = ssl.create_default_context()


def _read_env():
    creds = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip().strip("'\"")
    return creds


def _api(method, path, token=None, payload=None):
    req = urllib.request.Request(BASE + path, data=payload, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    return _api_request(req)


def get_token():
    """OAuth client_credentials token. Does not log/return the raw client secret."""
    creds = _read_env()
    basic = base64.b64encode(
        f"{creds['PAYPAL_CLIENT_ID']}:{creds['PAYPAL_CLIENT_SECRET']}".encode()
    ).decode()
    req = urllib.request.Request(
        BASE + "/v1/oauth2/token",
        data=b"grant_type=client_credentials",
        method="POST",
    )
    req.add_header("Authorization", f"Basic {basic}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    resp = _api_request(req)
    if isinstance(resp, dict) and "_http_error" in resp:
        return resp
    return resp.get("access_token")


def _api_request(req):
    try:
        with urllib.request.urlopen(req, context=_CTX, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code, "_body": e.read().decode()[:1200]}


def get_order(order_id):
    """GET /v2/checkout/orders/{id}"""
    token = get_token()
    return _api("GET", f"/v2/checkout/orders/{order_id}", token=token)


def get_capture(capture_id):
    """GET /v2/payments/captures/{id}"""
    token = get_token()
    return _api("GET", f"/v2/payments/captures/{capture_id}", token=token)


def resolve_capture_id(order_id):
    """order_id -> purchase_units[].payments.captures[0].id (ID契約 P0-1).

    Returns None if the order could not be fetched or has no captures.
    """
    order = get_order(order_id)
    if not isinstance(order, dict) or "_http_error" in order:
        return None
    purchase_units = order.get("purchase_units") or []
    for unit in purchase_units:
        captures = (unit.get("payments") or {}).get("captures") or []
        if captures:
            return captures[0].get("id")
    return None


def resolve_order_id(capture_id):
    """capture_id -> supplementary_data.related_ids.order_id (ID契約 P0-1).

    Returns None if the capture could not be fetched or related_ids/order_id absent.
    """
    capture = get_capture(capture_id)
    if not isinstance(capture, dict) or "_http_error" in capture:
        return None
    return (capture.get("supplementary_data") or {}).get("related_ids", {}).get("order_id")


def get_trackers(transaction_id):
    """GET /v1/shipping/trackers?transaction_id="""
    token = get_token()
    return _api("GET", f"/v1/shipping/trackers?transaction_id={transaction_id}", token=token)


def add_tracker(transaction_id, tracking_number, carrier, carrier_name_other=None):
    """POST /v1/shipping/trackers-batch

    Payload shape per SPEC §データモデル: tracking_number_type=CARRIER_PROVIDED.
    """
    token = get_token()
    tracker = {
        "transaction_id": transaction_id,
        "tracking_number": tracking_number,
        "status": "SHIPPED",
        "carrier": carrier,
    }
    if carrier_name_other is not None:
        tracker["carrier_name_other"] = carrier_name_other
    body = {
        "trackers": [tracker],
        "tracking_number_type": "CARRIER_PROVIDED",
    }
    return _api(
        "POST",
        "/v1/shipping/trackers-batch",
        token=token,
        payload=json.dumps(body).encode(),
    )

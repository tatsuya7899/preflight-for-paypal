"""localhost HTTP server for preflight-checker — stdlib http.server only.

Design source: SPEC-preflight-checker_design.md
  - "データモデル・インターフェース" (endpoint shapes: /check, /track, /health)
  - "非機能(性能・権限・セキュリティ・ログ)" (127.0.0.1-only bind, X-Preflight-Token,
    token file at ~/.config/studio/preflight-token mode 0600)
  - "ID契約(P0-1)" (order_id resolved to capture_id via paypal.resolve_capture_id)

This module wires backend/paypal.py + backend/rules.py + backend/meaning.py
together; it contains no PayPal/LLM/policy logic of its own.
"""
import json
import os
import secrets
import stat
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from backend import meaning, paypal, policy, rules

TOKEN_PATH = os.path.expanduser("~/.config/studio/preflight-token")
HOST = "127.0.0.1"
DEFAULT_PORT = 8000
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# --- fixture mode (judge-runnable path without PayPal credentials) -----------
# Enabled via `python3 -m backend.server --fixture` or PREFLIGHT_FIXTURE=1.
# In fixture mode /check resolves order_id/capture_id against
# backend/fixtures/order_*.json + capture_*.json instead of the live API, and
# /track appends to an in-memory tracker list so the register→re-check loop
# works end-to-end. /track still requires X-Preflight-Token (same auth path).
_fixture_mode = False
_fixture_orders = {}     # order_id -> order fixture dict
_fixture_captures = {}   # capture_id -> capture fixture dict
_fixture_trackers = {}   # capture_id -> [tracker dict, ...] (in-memory)


def _load_fixtures():
    for fn in os.listdir(FIXTURE_DIR):
        path = os.path.join(FIXTURE_DIR, fn)
        if fn.startswith("order_") and fn.endswith(".json"):
            with open(path) as f:
                order = json.load(f)
            _fixture_orders[order.get("id")] = order
        elif fn.startswith("capture_") and fn.endswith(".json"):
            with open(path) as f:
                capture = json.load(f)
            _fixture_captures[capture.get("id")] = capture


def _fixture_first_capture_id(order):
    for unit in order.get("purchase_units") or []:
        captures = (unit.get("payments") or {}).get("captures") or []
        if captures:
            return captures[0].get("id")
    return None


def _fixture_handle_check(body):
    """Mirror handle_check's resolution order against fixture data."""
    order_id = body.get("order_id")
    capture_id = body.get("capture_id")

    if not order_id and not capture_id:
        return 400, {"error": "capture_id or order_id is required"}

    if order_id and not capture_id:
        order = _fixture_orders.get(order_id)
        if order is not None:
            capture_id = _fixture_first_capture_id(order)
        if capture_id is None:
            return 404, {"error": "could not resolve capture_id from order_id (fixture)"}

    if not order_id:
        capture = _fixture_captures.get(capture_id)
        if capture is not None:
            order_id = (
                (capture.get("supplementary_data") or {})
                .get("related_ids", {}).get("order_id")
            )

    if not order_id:
        return 404, {"error": "could not resolve order_id from capture_id (fixture)"}

    order = _fixture_orders.get(order_id)
    if order is None:
        return 404, {"error": f"no fixture order for order_id={order_id}"}

    trackers = _fixture_trackers.get(capture_id, [])

    semantic_result = meaning.run(order)
    semantic = semantic_result["semantic"] if semantic_result["ran"] else None

    verdict = rules.evaluate(order, trackers, semantic)
    return 200, verdict


def _fixture_handle_track(body):
    """Mirror handle_track's validation, then append to the in-memory store."""
    capture_id = body.get("capture_id")
    tracking_number = body.get("tracking_number")
    carrier = body.get("carrier")
    carrier_name_other = body.get("carrier_name_other")

    if not capture_id or not tracking_number or not carrier:
        return 400, {"error": "capture_id, tracking_number and carrier are required"}
    if carrier not in policy.CARRIERS:
        return 400, {"error": f"carrier must be one of {policy.CARRIERS}"}
    if carrier == "OTHER" and not carrier_name_other:
        return 400, {"error": "carrier_name_other is required when carrier is OTHER"}
    if capture_id not in _fixture_captures:
        return 404, {"error": f"unknown capture_id in fixture mode: {capture_id}"}

    tracker = {
        "transaction_id": capture_id,
        "tracking_number": tracking_number,
        "status": "SHIPPED",
        "carrier": carrier,
    }
    if carrier_name_other is not None:
        tracker["carrier_name_other"] = carrier_name_other
    _fixture_trackers.setdefault(capture_id, []).append(tracker)
    return 200, {"trackers": _fixture_trackers[capture_id]}


def generate_token():
    """Generate a fresh token, write it to TOKEN_PATH with mode 0600, return it.

    Per design doc non-functional section: token is created at server startup
    and written to ~/.config/studio/preflight-token for the human to paste
    into the extension's options page once.
    """
    token = secrets.token_hex(32)
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    with open(TOKEN_PATH, "w") as f:
        f.write(token)
    os.chmod(TOKEN_PATH, stat.S_IRUSR | stat.S_IWUSR)
    return token


def read_token():
    """Read the token currently on disk at TOKEN_PATH, or None if absent."""
    try:
        with open(TOKEN_PATH) as f:
            return f.read().strip()
    except OSError:
        return None


def _is_http_error(resp):
    return isinstance(resp, dict) and "_http_error" in resp


def _http_error_status(resp):
    """Map a paypal.py `_http_error` dict to an HTTP status code to relay."""
    code = resp.get("_http_error")
    if isinstance(code, int) and 400 <= code < 600:
        return code
    return 502


def handle_check(body):
    """POST /check — resolve capture_id, fetch order+trackers, evaluate.

    Returns (status_code, response_dict).
    """
    if _fixture_mode:
        return _fixture_handle_check(body)
    order_id = body.get("order_id")
    capture_id = body.get("capture_id")

    if not order_id and not capture_id:
        return 400, {"error": "capture_id or order_id is required"}

    if order_id and not capture_id:
        capture_id = paypal.resolve_capture_id(order_id)
        if capture_id is None:
            return 404, {"error": "could not resolve capture_id from order_id"}

    if not order_id:
        order_id = paypal.resolve_order_id(capture_id)

    if order_id:
        order = paypal.get_order(order_id)
    else:
        # No order_id resolvable from the capture (design doc: "不在時はorder_id
        # =nullで返し、コンソールからの手動order_id入力を促す"). Without an
        # order we cannot build purchase_units for the rule layer.
        return 404, {"error": "could not resolve order_id from capture_id"}

    if _is_http_error(order):
        return _http_error_status(order), order

    trackers_resp = paypal.get_trackers(capture_id)
    if _is_http_error(trackers_resp):
        return _http_error_status(trackers_resp), trackers_resp
    trackers = trackers_resp.get("trackers") if isinstance(trackers_resp, dict) else None

    semantic_result = meaning.run(order)
    semantic = semantic_result["semantic"] if semantic_result["ran"] else None

    verdict = rules.evaluate(order, trackers, semantic)
    return 200, verdict


def handle_track(body):
    """POST /track — register a tracking number, return the read-back trackers.

    Returns (status_code, response_dict). Token check happens in the handler
    (needs request headers, not just the body).
    """
    if _fixture_mode:
        return _fixture_handle_track(body)
    capture_id = body.get("capture_id")
    tracking_number = body.get("tracking_number")
    carrier = body.get("carrier")
    carrier_name_other = body.get("carrier_name_other")

    if not capture_id or not tracking_number or not carrier:
        return 400, {"error": "capture_id, tracking_number and carrier are required"}
    if carrier not in policy.CARRIERS:
        return 400, {"error": f"carrier must be one of {policy.CARRIERS}"}
    if carrier == "OTHER" and not carrier_name_other:
        return 400, {"error": "carrier_name_other is required when carrier is OTHER"}

    add_resp = paypal.add_tracker(capture_id, tracking_number, carrier, carrier_name_other)
    if _is_http_error(add_resp):
        return _http_error_status(add_resp), add_resp

    trackers_resp = paypal.get_trackers(capture_id)
    if _is_http_error(trackers_resp):
        return _http_error_status(trackers_resp), trackers_resp

    return 200, trackers_resp


class PreflightHandler(BaseHTTPRequestHandler):
    server_version = "preflight-checker/1"

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw)

    def log_message(self, fmt, *args):
        # Do not leak request contents (tokens, etc.) into stdout logs.
        pass

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {
                "ok": True,
                "llm": meaning.llm_available(),
                "fixture": _fixture_mode,
            })
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._read_json_body()
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "invalid JSON body"})
            return

        if self.path == "/check":
            status, payload = handle_check(body)
            self._send_json(status, payload)
            return

        if self.path == "/track":
            token = self.headers.get("X-Preflight-Token")
            expected = read_token()
            if not token or not expected or token != expected:
                self._send_json(403, {"error": "missing or invalid X-Preflight-Token"})
                return
            status, payload = handle_track(body)
            self._send_json(status, payload)
            return

        self._send_json(404, {"error": "not found"})


def make_server(port=None, fixture=None):
    global _fixture_mode
    if fixture is None:
        fixture = os.environ.get("PREFLIGHT_FIXTURE", "").lower() in ("1", "true", "yes")
    _fixture_mode = bool(fixture)
    if _fixture_mode:
        _load_fixtures()
    port = port or int(os.environ.get("PREFLIGHT_PORT", DEFAULT_PORT))
    generate_token()
    return HTTPServer((HOST, port), PreflightHandler)


def main():
    fixture = "--fixture" in sys.argv
    server = make_server(fixture=fixture)
    if fixture:
        print(
            f"preflight-checker fixture mode — {len(_fixture_orders)} orders, "
            f"{len(_fixture_captures)} captures loaded from {FIXTURE_DIR}",
            file=sys.stderr,
        )
        print(f"token written to {TOKEN_PATH}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

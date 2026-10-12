"""Tests for backend/server.py (localhost HTTP server).

Test basis: SPEC-preflight-checker_design.md
  - "データモデル・インターフェース" section (GET /health, POST /check, POST /track
    request/response shapes)
  - "非機能(性能・権限・セキュリティ・ログ)" section (X-Preflight-Token required on
    /track, 403 on missing/invalid token, carrier OTHER requires carrier_name_other,
    PayPal API errors are relayed with upstream status rather than flattened to 500)
  - "ID契約(P0-1)" section (order_id input resolved to capture_id via
    paypal.resolve_capture_id before evaluation)

Written from the design spec's endpoint contracts, not from reading server.py's
implementation. PayPal/LLM calls are mocked — no real network access.
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend import server

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "backend", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


def _fixture_names():
    return [f for f in os.listdir(FIXTURES) if f.startswith("order_")]


class _LiveServerBase(unittest.TestCase):
    """Spin up a real localhost server (fixture=False, throwaway token file)
    so tests exercise the actual HTTP handler, not re-derived payloads."""

    def setUp(self):
        import threading
        import http.client

        self.http_client = http.client
        self._token_patch = mock.patch.object(
            server, "TOKEN_PATH", "/tmp/preflight-token-test-" + os.urandom(4).hex()
        )
        self._token_patch.start()
        # fixture=False explicitly: make_server() would otherwise read
        # PREFLIGHT_FIXTURE from the environment and silently switch modes
        # when pytest runs with the variable exported.
        self.httpd = server.make_server(port=0, fixture=False)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        # Remove the throwaway token BEFORE stopping the patch — after stop(),
        # server.TOKEN_PATH is the real ~/.config/studio/preflight-token again
        # and removing it would silently break auth on a running dev instance.
        try:
            os.remove(server.TOKEN_PATH)
        except OSError:
            pass
        self._token_patch.stop()

    def _post(self, path, body, headers=None):
        conn = self.http_client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", path, body=json.dumps(body),
                     headers={"Content-Type": "application/json", **(headers or {})})
        resp = conn.getresponse()
        status = resp.status
        payload = json.loads(resp.read() or b"{}")
        conn.close()
        return status, payload


class HealthTest(_LiveServerBase):
    """Drive /health through the real handler — a self-asserted dict would
    prove nothing about what the server actually returns."""

    def _health(self):
        conn = self.http_client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        payload = json.loads(resp.read())
        conn.close()
        return payload

    def test_health_reports_llm_flag_true(self):
        with mock.patch.object(server.meaning, "llm_available", return_value=True):
            payload = self._health()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["llm"])

    def test_health_reports_llm_flag_false(self):
        with mock.patch.object(server.meaning, "llm_available", return_value=False):
            payload = self._health()
        self.assertFalse(payload["llm"])


class RequestValidationTest(_LiveServerBase):
    """Live-side degenerate inputs — the fixture path mocks these away."""

    def test_oversize_content_length_is_413(self):
        # The server must reject on the header alone, before reading a body.
        conn = self.http_client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/check")
        conn.putheader("Content-Length", str(server.MAX_BODY_BYTES + 1))
        conn.endheaders(b"")
        resp = conn.getresponse()
        status = resp.status
        resp.read()
        conn.close()
        self.assertEqual(status, 413)

    def test_negative_content_length_is_400(self):
        # rfile.read(-1) would block until EOF and stall this single-threaded
        # server — a negative length must be refused outright. Needs a raw
        # socket; http.client will not send a negative Content-Length.
        import socket as _socket
        s = _socket.create_connection(("127.0.0.1", self.port), timeout=5)
        s.sendall(b"POST /check HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                  b"Content-Length: -1\r\nConnection: close\r\n\r\n")
        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
        s.close()
        status_line = b"".join(chunks).split(b"\r\n", 1)[0]
        self.assertIn(b" 400 ", status_line)

    def test_malformed_json_is_400(self):
        conn = self.http_client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/check", body=b"{not json",
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        status = resp.status
        payload = json.loads(resp.read() or b"{}")
        conn.close()
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_handler_exception_returns_500_not_dropped_connection(self):
        # An uncaught exception in handle_* must surface as 500 — otherwise
        # the panel cannot tell a crash from "backend offline".
        with mock.patch.object(server, "handle_check", side_effect=KeyError("boom")):
            status, payload = self._post("/check", {"capture_id": "X"})
        self.assertEqual(status, 500)
        self.assertIn("error", payload)


class HandleCheckTest(unittest.TestCase):
    def setUp(self):
        fixtures = _fixture_names()
        if not fixtures:
            self.skipTest("no order_*.json fixtures available")
        self.order = load_fixture(fixtures[0])
        self.capture_id = (
            self.order["purchase_units"][0]["payments"]["captures"][0]["id"]
        )

    def test_check_by_capture_id_returns_verdict(self):
        with mock.patch.object(server.paypal, "resolve_order_id", return_value=self.order["id"]), \
             mock.patch.object(server.paypal, "get_order", return_value=self.order), \
             mock.patch.object(server.paypal, "get_trackers", return_value={"trackers": []}), \
             mock.patch.object(server.meaning, "run", return_value={"ran": False, "semantic": None,
                                                                      "fraud_warnings": [], "unassessable_patterns": []}):
            status, verdict = server.handle_check({"capture_id": self.capture_id})

        self.assertEqual(status, 200)
        self.assertEqual(verdict["order_id"], self.order["id"])
        self.assertIn("checks", verdict)
        self.assertIn("summary", verdict)
        self.assertIn("flags", verdict)

    def test_check_by_order_id_resolves_capture_id(self):
        with mock.patch.object(server.paypal, "get_order", return_value=self.order) as get_order, \
             mock.patch.object(server.paypal, "get_trackers", return_value={"trackers": []}), \
             mock.patch.object(server.meaning, "run", return_value={"ran": False, "semantic": None,
                                                                      "fraud_warnings": [], "unassessable_patterns": []}):
            status, verdict = server.handle_check({"order_id": self.order["id"]})

        # The order is fetched exactly once — capture_id is derived from that
        # same response rather than a second order GET (design: one order GET
        # per /check).
        get_order.assert_called_once_with(self.order["id"])
        self.assertEqual(status, 200)
        self.assertEqual(verdict["capture_id"], self.capture_id)

    def test_check_with_both_ids_uses_them_without_resolution(self):
        with mock.patch.object(server.paypal, "get_order", return_value=self.order) as get_order, \
             mock.patch.object(server.paypal, "resolve_order_id") as roid, \
             mock.patch.object(server.paypal, "get_trackers", return_value={"trackers": []}), \
             mock.patch.object(server.meaning, "run", return_value={"ran": False, "semantic": None,
                                                                      "fraud_warnings": [], "unassessable_patterns": []}):
            status, verdict = server.handle_check(
                {"order_id": self.order["id"], "capture_id": self.capture_id})

        roid.assert_not_called()
        get_order.assert_called_once_with(self.order["id"])
        self.assertEqual(status, 200)
        self.assertEqual(verdict["capture_id"], self.capture_id)

    def test_check_tolerates_trackers_null(self):
        """A live `{"trackers": null}` response passes None into evaluate() —
        the check must still produce a verdict rather than crash."""
        with mock.patch.object(server.paypal, "resolve_order_id", return_value=self.order["id"]), \
             mock.patch.object(server.paypal, "get_order", return_value=self.order), \
             mock.patch.object(server.paypal, "get_trackers", return_value={"trackers": None}), \
             mock.patch.object(server.meaning, "run", return_value={"ran": False, "semantic": None,
                                                                      "fraud_warnings": [], "unassessable_patterns": []}):
            status, verdict = server.handle_check({"capture_id": self.capture_id})

        self.assertEqual(status, 200)
        self.assertIn("checks", verdict)

    def test_check_by_order_id_relays_upstream_error(self):
        error_resp = {"_http_error": 404, "_body": "NOT_FOUND"}
        with mock.patch.object(server.paypal, "get_order", return_value=error_resp):
            status, payload = server.handle_check({"order_id": self.order["id"]})

        self.assertEqual(status, 404)
        self.assertEqual(payload, error_resp)

    def test_check_relays_upstream_http_error_status(self):
        error_resp = {"_http_error": 404, "_body": "NOT_FOUND"}
        with mock.patch.object(server.paypal, "resolve_order_id", return_value=self.order["id"]), \
             mock.patch.object(server.paypal, "get_order", return_value=error_resp):
            status, payload = server.handle_check({"capture_id": self.capture_id})

        self.assertEqual(status, 404)
        self.assertEqual(payload, error_resp)

    def test_check_requires_capture_id_or_order_id(self):
        status, payload = server.handle_check({})
        self.assertEqual(status, 400)
        self.assertIn("error", payload)


class HandleTrackTest(unittest.TestCase):
    def test_track_otherwise_valid_registers_and_reads_back(self):
        add_resp = {"trackers": [{"transaction_id": "CAP1", "status": "SHIPPED"}]}
        readback = {"trackers": [{"transaction_id": "CAP1", "status": "SHIPPED",
                                   "tracking_number": "1Z999"}]}
        with mock.patch.object(server.paypal, "add_tracker", return_value=add_resp) as add, \
             mock.patch.object(server.paypal, "get_trackers", return_value=readback):
            status, payload = server.handle_track({
                "capture_id": "CAP1",
                "tracking_number": "1Z999",
                "carrier": "UPS",
            })

        add.assert_called_once_with("CAP1", "1Z999", "UPS", None)
        self.assertEqual(status, 200)
        self.assertEqual(payload, readback)

    def test_track_other_carrier_requires_carrier_name_other(self):
        status, payload = server.handle_track({
            "capture_id": "CAP1",
            "tracking_number": "1Z999",
            "carrier": "OTHER",
        })
        self.assertEqual(status, 400)
        self.assertIn("error", payload)

    def test_track_other_carrier_with_name_succeeds(self):
        with mock.patch.object(server.paypal, "add_tracker", return_value={}) as add, \
             mock.patch.object(server.paypal, "get_trackers", return_value={"trackers": []}):
            status, payload = server.handle_track({
                "capture_id": "CAP1",
                "tracking_number": "1Z999",
                "carrier": "OTHER",
                "carrier_name_other": "Regional Courier Co",
            })
        add.assert_called_once_with("CAP1", "1Z999", "OTHER", "Regional Courier Co")
        self.assertEqual(status, 200)

    def test_track_relays_upstream_http_error_status(self):
        error_resp = {"_http_error": 422, "_body": "INVALID_TRACKING_NUMBER"}
        with mock.patch.object(server.paypal, "add_tracker", return_value=error_resp):
            status, payload = server.handle_track({
                "capture_id": "CAP1",
                "tracking_number": "bad",
                "carrier": "UPS",
            })
        self.assertEqual(status, 422)
        self.assertEqual(payload, error_resp)

    def test_track_rejects_invalid_carrier(self):
        status, payload = server.handle_track({
            "capture_id": "CAP1",
            "tracking_number": "1Z999",
            "carrier": "SPACE_FREIGHT",
        })
        self.assertEqual(status, 400)
        self.assertIn("error", payload)


class FixtureModeTest(unittest.TestCase):
    """Fixture mode (--fixture / PREFLIGHT_FIXTURE): no PayPal calls, the
    register→re-check loop works against backend/fixtures/* data."""

    def setUp(self):
        self._prev = server._fixture_mode
        self._prev_orders = dict(server._fixture_orders)
        self._prev_captures = dict(server._fixture_captures)
        self._prev_trackers = dict(server._fixture_trackers)
        self._prev_disputes = dict(server._fixture_disputes)
        server._fixture_orders.clear()
        server._fixture_captures.clear()
        server._fixture_trackers.clear()
        server._fixture_disputes.clear()
        server._load_fixtures()
        server._fixture_mode = True
        # file docstring: no real network access — the LLM layer must be
        # mocked too, not just paypal (a machine with a real API key set
        # would otherwise hit the network mid-test).
        self._meaning_patch = mock.patch.object(
            server.meaning, "run",
            return_value={"ran": False, "semantic": None,
                          "fraud_warnings": [], "unassessable_patterns": []})
        self._meaning_patch.start()
        if not server._fixture_orders:
            self.skipTest("no order_*.json fixtures available")

    def tearDown(self):
        self._meaning_patch.stop()
        server._fixture_mode = self._prev
        server._fixture_orders.clear()
        server._fixture_orders.update(self._prev_orders)
        server._fixture_captures.clear()
        server._fixture_captures.update(self._prev_captures)
        server._fixture_trackers.clear()
        server._fixture_trackers.update(self._prev_trackers)
        server._fixture_disputes.clear()
        server._fixture_disputes.update(self._prev_disputes)

    def test_check_by_order_id_returns_verdict(self):
        order_id = sorted(server._fixture_orders)[0]
        status, verdict = server.handle_check({"order_id": order_id})
        self.assertEqual(status, 200)
        self.assertEqual(verdict["order_id"], order_id)
        self.assertIn("checks", verdict)
        self.assertIn("flags", verdict)

    def test_check_by_capture_id_resolves_order(self):
        capture_id = sorted(server._fixture_captures)[0]
        status, verdict = server.handle_check({"capture_id": capture_id})
        self.assertEqual(status, 200)
        self.assertIsNotNone(verdict["order_id"])

    def test_check_unknown_order_id_is_404(self):
        status, payload = server.handle_check({"order_id": "NO_SUCH_ORDER_000"})
        self.assertEqual(status, 404)
        self.assertIn("error", payload)

    def test_track_then_recheck_closes_the_loop(self):
        """The judge-visible demo loop: fail → register → re-check passes."""
        capture_id = sorted(server._fixture_captures)[0]
        status, before = server.handle_check({"capture_id": capture_id})
        self.assertEqual(status, 200)
        tracking = next(c for c in before["checks"]
                        if c["condition"] == "TRACKING_REQUIRED")
        self.assertEqual(tracking["status"], "fail")  # fixture has no trackers

        status, payload = server.handle_track({
            "capture_id": capture_id,
            "tracking_number": "1Z999AA10123456784",
            "carrier": "UPS",
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["trackers"][0]["tracking_number"],
                         "1Z999AA10123456784")

        status, after = server.handle_check({"capture_id": capture_id})
        self.assertEqual(status, 200)
        tracking = next(c for c in after["checks"]
                        if c["condition"] == "TRACKING_REQUIRED")
        self.assertEqual(tracking["status"], "pass")

    def test_track_unknown_capture_id_is_404(self):
        status, payload = server.handle_track({
            "capture_id": "NO_SUCH_CAPTURE_00",
            "tracking_number": "1Z999",
            "carrier": "UPS",
        })
        self.assertEqual(status, 404)

    def test_check_attaches_dispute_summary_for_disputed_capture(self):
        """The disputed fixture capture (3J366679AY2283450, dispute
        PP-R-XGB-10190971) gets a slim dispute block — the Act-3
        correspondence the demo shows."""
        status, verdict = server.handle_check(
            {"capture_id": "3J366679AY2283450"})
        self.assertEqual(status, 200)
        self.assertIn("dispute", verdict)
        d = verdict["dispute"]
        self.assertEqual(d["dispute_id"], "PP-R-XGB-10190971")
        self.assertEqual(d["reason"], "MERCHANDISE_OR_SERVICE_NOT_RECEIVED")
        self.assertIn("PROOF_OF_FULFILLMENT", d["evidence_types"])
        self.assertIn("fixture", d["source"])
        # No buyer PII is forwarded into the verdict.
        self.assertNotIn("buyer", json.dumps(d))
        self.assertNotIn("email", json.dumps(d))

    def test_check_omits_dispute_for_clean_capture(self):
        """Captures with no dispute fixture carry no `dispute` key at all —
        the panel hides the banner rather than showing fabricated data."""
        status, verdict = server.handle_check(
            {"capture_id": "4EC24563F7235632E"})  # order A — no dispute fixture
        self.assertEqual(status, 200)
        self.assertNotIn("dispute", verdict)


class TokenAuthTest(_LiveServerBase):
    """X-Preflight-Token gate on /track, exercised through the live HTTP server."""

    def test_track_without_token_is_403(self):
        status, payload = self._post("/track", {
            "capture_id": "CAP1", "tracking_number": "1Z999", "carrier": "UPS",
        })
        self.assertEqual(status, 403)

    def test_track_with_wrong_token_is_403(self):
        status, payload = self._post("/track", {
            "capture_id": "CAP1", "tracking_number": "1Z999", "carrier": "UPS",
        }, headers={"X-Preflight-Token": "wrong-token"})
        self.assertEqual(status, 403)

    def test_track_with_correct_token_passes_auth(self):
        token = server.read_token()
        with mock.patch.object(server.paypal, "add_tracker", return_value={}), \
             mock.patch.object(server.paypal, "get_trackers", return_value={"trackers": []}):
            status, payload = self._post("/track", {
                "capture_id": "CAP1", "tracking_number": "1Z999", "carrier": "UPS",
            }, headers={"X-Preflight-Token": token})
        self.assertEqual(status, 200)

    def test_health_does_not_require_token(self):
        conn = self.http_client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        status = resp.status
        payload = json.loads(resp.read())
        conn.close()
        self.assertEqual(status, 200)
        self.assertIn("ok", payload)
        self.assertIn("llm", payload)
        self.assertIn("fixture", payload)
        self.assertFalse(payload["fixture"])


if __name__ == "__main__":
    unittest.main()

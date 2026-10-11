"""Unit tests for backend/paypal.py — no real API calls (mocked urllib).

Root in SPEC-preflight-checker_design.md:
- "ID契約(P0-1)": capture_id resolution from order (purchase_units[].payments.captures[0].id)
  and reverse resolution from capture via supplementary_data.related_ids.order_id
  (absent -> order_id=null).
- "触るファイル": backend/paypal.py — OAuth・Orders取得・trackers-batch POST/trackers GET
  (既存sandbox/*.pyのロジック移植).
- non-functional: HTTPエラーはdict `{"_http_error": code, "_body": ...}` (既存パターン踏襲).
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import paypal  # noqa: E402


FIXTURES = os.path.join(os.path.dirname(__file__), "..", "backend", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


class ResolveCaptureIdTest(unittest.TestCase):
    """SPEC §ID契約(P0-1): order_id -> purchase_units[].payments.captures[0].id"""

    def test_returns_first_capture_id_from_order(self):
        order = load_fixture("order_A.json")
        with mock.patch.object(paypal, "get_order", return_value=order):
            result = paypal.resolve_capture_id("2YD26664U8090205J")
        self.assertEqual(result, "4EC24563F7235632E")

    def test_returns_none_when_no_captures_present(self):
        order_without_captures = {
            "id": "XXX",
            "purchase_units": [{"payments": {"captures": []}}],
        }
        with mock.patch.object(paypal, "get_order", return_value=order_without_captures):
            result = paypal.resolve_capture_id("XXX")
        self.assertIsNone(result)

    def test_returns_none_on_http_error(self):
        with mock.patch.object(
            paypal, "get_order", return_value={"_http_error": 404, "_body": "not found"}
        ):
            result = paypal.resolve_capture_id("NOPE")
        self.assertIsNone(result)


class ResolveOrderIdTest(unittest.TestCase):
    """SPEC §ID契約(P0-1): capture_id -> supplementary_data.related_ids.order_id
    (不在時はNone)。"""

    def test_returns_order_id_from_capture(self):
        capture = load_fixture("capture_A_physical_with_addr.json")
        with mock.patch.object(paypal, "get_capture", return_value=capture):
            result = paypal.resolve_order_id("4EC24563F7235632E")
        self.assertEqual(result, "2YD26664U8090205J")

    def test_returns_none_when_related_ids_missing(self):
        capture_without_related_ids = {"id": "ZZZ", "supplementary_data": {}}
        with mock.patch.object(paypal, "get_capture", return_value=capture_without_related_ids):
            result = paypal.resolve_order_id("ZZZ")
        self.assertIsNone(result)

    def test_returns_none_when_supplementary_data_missing(self):
        with mock.patch.object(paypal, "get_capture", return_value={"id": "ZZZ"}):
            result = paypal.resolve_order_id("ZZZ")
        self.assertIsNone(result)


class AddTrackerPayloadTest(unittest.TestCase):
    """SPEC §データモデル `POST /track` / tracking_number_type=CARRIER_PROVIDED"""

    def test_payload_structure_carrier_provided(self):
        captured = {}

        def fake_api(method, path, token=None, payload=None):
            captured["method"] = method
            captured["path"] = path
            captured["payload"] = json.loads(payload)
            return {"trackers": [{"transaction_id": "TXN1"}]}

        with mock.patch.object(paypal, "_api", side_effect=fake_api), \
                mock.patch.object(paypal, "get_token", return_value="tok"):
            result = paypal.add_tracker("TXN1", "1Z999AA10123456784", "UPS")

        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/v1/shipping/trackers-batch")
        body = captured["payload"]
        self.assertEqual(body["tracking_number_type"], "CARRIER_PROVIDED")
        self.assertEqual(len(body["trackers"]), 1)
        tracker = body["trackers"][0]
        self.assertEqual(tracker["transaction_id"], "TXN1")
        self.assertEqual(tracker["tracking_number"], "1Z999AA10123456784")
        self.assertEqual(tracker["carrier"], "UPS")
        self.assertNotIn("carrier_name_other", tracker)
        self.assertEqual(result, {"trackers": [{"transaction_id": "TXN1"}]})

    def test_payload_includes_carrier_name_other_when_given(self):
        captured = {}

        def fake_api(method, path, token=None, payload=None):
            captured["payload"] = json.loads(payload)
            return {}

        with mock.patch.object(paypal, "_api", side_effect=fake_api), \
                mock.patch.object(paypal, "get_token", return_value="tok"):
            paypal.add_tracker("TXN1", "ABC123", "OTHER", carrier_name_other="Local Courier")

        tracker = captured["payload"]["trackers"][0]
        self.assertEqual(tracker["carrier"], "OTHER")
        self.assertEqual(tracker["carrier_name_other"], "Local Courier")


class GetTokenEnvNotLeakedTest(unittest.TestCase):
    """非機能: 秘匿(client_secret等をログ・レスポンスに出さない)。
    get_token()の戻り値が生の認証情報文字列を含まないことを確認する。"""

    def test_token_response_does_not_contain_raw_secret(self):
        fake_env = "PAYPAL_CLIENT_ID=abc\nPAYPAL_CLIENT_SECRET=supersecret\n"
        with mock.patch("builtins.open", mock.mock_open(read_data=fake_env)), \
                mock.patch.object(
                    paypal, "_api_request", return_value={"access_token": "tok123"}
                ):
            token = paypal.get_token()
        self.assertEqual(token, "tok123")
        self.assertNotIn("supersecret", repr(token))


if __name__ == "__main__":
    unittest.main()

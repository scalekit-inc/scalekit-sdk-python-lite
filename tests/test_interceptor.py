"""Unit tests for verify_interceptor_payload. No network required."""

import base64
import hashlib
import hmac
import time
import unittest

from scalekit._core import ScalekitError
from scalekit.client import ScalekitClient


def _sign(secret_b64, msg_id, ts, payload):
    secret_bytes = base64.b64decode(secret_b64)
    data = "{}.{}.{}".format(msg_id, ts, payload)
    sig = hmac.new(secret_bytes, data.encode("utf-8"), hashlib.sha256).digest()
    return "v1,{}".format(base64.b64encode(sig).decode("utf-8"))


class TestVerifyInterceptorPayload(unittest.TestCase):
    def setUp(self):
        self.client = ScalekitClient(
            env_url="https://example.scalekit.cloud",
            client_id="skc_test",
            client_secret="test_secret",
        )
        self.secret_b64 = base64.b64encode(b"supersecretbytes").decode("utf-8")
        self.secret = "icpsec_" + self.secret_b64

    def test_valid_interceptor_signature(self):
        ts = str(int(time.time()))
        payload = "{}"
        headers = {
            "interceptor-id": "msg_1",
            "interceptor-timestamp": ts,
            "interceptor-signature": _sign(self.secret_b64, "msg_1", ts, payload),
        }
        self.assertTrue(self.client.verify_interceptor_payload(self.secret, headers, payload))

    def test_falls_back_to_webhook_headers(self):
        ts = str(int(time.time()))
        payload = "{}"
        headers = {
            "webhook-id": "msg_2",
            "webhook-timestamp": ts,
            "webhook-signature": _sign(self.secret_b64, "msg_2", ts, payload),
        }
        self.assertTrue(self.client.verify_interceptor_payload(self.secret, headers, payload))

    def test_invalid_signature_raises(self):
        ts = str(int(time.time()))
        headers = {
            "interceptor-id": "msg_3",
            "interceptor-timestamp": ts,
            "interceptor-signature": "v1,badsignature==",
        }
        with self.assertRaises(ScalekitError):
            self.client.verify_interceptor_payload(self.secret, headers, "{}")

    def test_missing_headers_raises(self):
        with self.assertRaises(ScalekitError):
            self.client.verify_interceptor_payload(self.secret, {}, "{}")


if __name__ == "__main__":
    unittest.main()

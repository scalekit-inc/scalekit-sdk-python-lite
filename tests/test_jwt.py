"""Unit tests for _jwt.py using an in-process RSA key pair. No network required."""

import base64
import json
import sys
import time
import unittest

import rsa
import rsa.pkcs1

# ---------------------------------------------------------------------------
# Helpers to build a minimal JWT with our own key
# ---------------------------------------------------------------------------

def _b64url(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _make_jwt(payload, private_key, kid="test-kid", alg="RS256"):
    header = {"alg": alg, "kid": kid, "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")))
    signing_input = "{}.{}".format(header_b64, payload_b64).encode("ascii")
    signature = rsa.sign(signing_input, private_key, "SHA-256")
    sig_b64 = _b64url(signature)
    return "{}.{}.{}".format(header_b64, payload_b64, sig_b64)


def _int_to_b64url(n):
    length = (n.bit_length() + 7) // 8
    raw = n.to_bytes(length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


# ---------------------------------------------------------------------------
# Stub CoreClient — returns a canned JWKS without any network call
# ---------------------------------------------------------------------------

class StubCore(object):
    def __init__(self, jwks):
        self._jwks = jwks

    def request(self, method, path, body=None, params=None):
        if path == "/keys":
            return {"keys": self._jwks}
        raise AssertionError("Unexpected request: {} {}".format(method, path))


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestJwtValidator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Generate a 512-bit key pair once for the whole test class.
        # 512-bit is insecure but fast for tests — never use in production.
        (cls.pub_key, cls.priv_key) = rsa.newkeys(512, poolsize=1)
        cls.kid = "test-kid-1"
        cls.jwk = {
            "kty": "RSA",
            "kid": cls.kid,
            "n": _int_to_b64url(cls.pub_key.n),
            "e": _int_to_b64url(cls.pub_key.e),
        }
        cls.stub_core = StubCore([cls.jwk])

    def _make_validator(self):
        from scalekit._jwt import JwtValidator
        return JwtValidator(self.stub_core)

    def _valid_payload(self):
        now = int(time.time())
        return {
            "sub": "user-123",
            "iss": "https://example.scalekit.com",
            "aud": "my-client",
            "iat": now,
            "exp": now + 3600,
        }

    def test_valid_token(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        result = validator.validate(token)
        self.assertEqual(result["sub"], "user-123")

    def test_issuer_check_pass(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        result = validator.validate(token, issuer="https://example.scalekit.com")
        self.assertEqual(result["iss"], "https://example.scalekit.com")

    def test_issuer_check_fail(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        with self.assertRaises(ValueError) as ctx:
            validator.validate(token, issuer="https://wrong.example.com")
        self.assertIn("issuer mismatch", str(ctx.exception))

    def test_audience_check_pass(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        result = validator.validate(token, audience="my-client")
        self.assertIsNotNone(result)

    def test_audience_check_fail(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        with self.assertRaises(ValueError) as ctx:
            validator.validate(token, audience="wrong-client")
        self.assertIn("audience mismatch", str(ctx.exception))

    def test_expired_token(self):
        validator = self._make_validator()
        now = int(time.time())
        payload = {
            "sub": "user-456",
            "iat": now - 7200,
            "exp": now - 3600,  # already expired
        }
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        with self.assertRaises(ValueError) as ctx:
            validator.validate(token)
        self.assertIn("expired", str(ctx.exception))

    def test_nbf_not_yet_valid(self):
        validator = self._make_validator()
        now = int(time.time())
        payload = {
            "sub": "user-789",
            "iat": now,
            "exp": now + 3600,
            "nbf": now + 600,  # valid only in 10 minutes
        }
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        with self.assertRaises(ValueError) as ctx:
            validator.validate(token)
        self.assertIn("not yet valid", str(ctx.exception))

    def test_tampered_signature(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        # Flip the last character of the signature part
        parts = token.split(".")
        sig = parts[2]
        # Change first char to corrupt the signature
        corrupted = ("A" if sig[0] != "A" else "B") + sig[1:]
        bad_token = ".".join(parts[:2] + [corrupted])
        with self.assertRaises(ValueError) as ctx:
            validator.validate(bad_token)
        self.assertIn("signature verification failed", str(ctx.exception))

    def test_unknown_kid(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid="unknown-kid")
        with self.assertRaises(ValueError) as ctx:
            validator.validate(token)
        self.assertIn("No JWK found", str(ctx.exception))

    def test_unsupported_algorithm(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        # Build a token with alg=HS256 in the header
        token = _make_jwt(payload, self.priv_key, kid=self.kid, alg="HS256")
        with self.assertRaises(ValueError) as ctx:
            validator.validate(token)
        self.assertIn("Unsupported algorithm", str(ctx.exception))

    def test_invalid_format(self):
        validator = self._make_validator()
        with self.assertRaises(ValueError):
            validator.validate("not.a.valid.jwt.format.extra")

    def test_decode_without_verification(self):
        validator = self._make_validator()
        payload = self._valid_payload()
        token = _make_jwt(payload, self.priv_key, kid=self.kid)
        decoded = validator.decode_without_verification(token)
        self.assertEqual(decoded["sub"], "user-123")

    def test_jwks_cache(self):
        """JWKS should be fetched only once within the cache TTL."""
        call_count = [0]
        original_request = self.stub_core.request

        def counting_request(method, path, body=None, params=None):
            if path == "/keys":
                call_count[0] += 1
            return original_request(method, path, body=body, params=params)

        self.stub_core.request = counting_request
        try:
            from scalekit._jwt import JwtValidator
            validator = JwtValidator(self.stub_core)
            payload = self._valid_payload()
            token = _make_jwt(payload, self.priv_key, kid=self.kid)
            validator.validate(token)
            validator.validate(token)
            self.assertEqual(call_count[0], 1, "JWKS should be cached after first fetch")
        finally:
            self.stub_core.request = original_request


if __name__ == "__main__":
    unittest.main()

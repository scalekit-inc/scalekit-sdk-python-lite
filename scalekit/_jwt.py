"""JWT RS256 validation using the rsa package."""

import base64
import json
import time

import rsa
import rsa.pkcs1

try:
    from typing import Any, Dict, Optional
except ImportError:
    pass

_JWKS_CACHE_TTL = 3600  # seconds


def _decode_base64url(s):
    """Decode a base64url string, adding padding as needed."""
    if isinstance(s, str):
        s = s.encode("ascii")
    padding = (4 - len(s) % 4) % 4
    s = s + b"=" * padding
    return base64.urlsafe_b64decode(s)


def _base64url_to_int(s):
    """Decode base64url to a big-endian integer."""
    raw = _decode_base64url(s)
    return int.from_bytes(raw, "big")


class JwtValidator(object):
    """Validates RS256 JWTs against JWKS fetched from the Scalekit environment."""

    def __init__(self, core_client):
        self._core = core_client
        self._jwks_cache = None
        self._jwks_fetched_at = 0

    def _get_jwks(self):
        now = time.time()
        if self._jwks_cache and now - self._jwks_fetched_at < _JWKS_CACHE_TTL:
            return self._jwks_cache
        resp = self._core.request("GET", "/keys")
        self._jwks_cache = resp.get("keys", [])
        self._jwks_fetched_at = now
        return self._jwks_cache

    def _find_jwk(self, kid):
        keys = self._get_jwks()
        for key in keys:
            if key.get("kid") == kid:
                return key
        # Retry once after clearing cache (key rotation)
        self._jwks_cache = None
        keys = self._get_jwks()
        for key in keys:
            if key.get("kid") == kid:
                return key
        return None

    def validate(self, token, issuer=None, audience=None):
        """Validate an RS256 JWT and return the decoded payload dict."""
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format: expected 3 parts")

        header_b64, payload_b64, sig_b64 = parts

        header = json.loads(_decode_base64url(header_b64).decode("utf-8"))
        if header.get("alg") != "RS256":
            raise ValueError("Unsupported algorithm: {}".format(header.get("alg")))

        kid = header.get("kid")
        jwk = self._find_jwk(kid)
        if jwk is None:
            raise ValueError("No JWK found for kid: {}".format(kid))

        n = _base64url_to_int(jwk["n"])
        e = _base64url_to_int(jwk["e"])
        pub_key = rsa.PublicKey(n, e)

        signing_input = "{}.{}".format(header_b64, payload_b64).encode("ascii")
        signature = _decode_base64url(sig_b64)

        try:
            rsa.verify(signing_input, signature, pub_key)
        except rsa.pkcs1.VerificationError:
            raise ValueError("JWT signature verification failed")

        payload = json.loads(_decode_base64url(payload_b64).decode("utf-8"))

        now = time.time()
        if "exp" in payload and now > payload["exp"]:
            raise ValueError("JWT has expired")
        if "nbf" in payload and now < payload["nbf"]:
            raise ValueError("JWT is not yet valid")
        if issuer is not None and payload.get("iss") != issuer:
            raise ValueError(
                "JWT issuer mismatch: expected {!r}, got {!r}".format(
                    issuer, payload.get("iss")
                )
            )
        if audience is not None:
            aud = payload.get("aud", [])
            if isinstance(aud, str):
                aud = [aud]
            if audience not in aud:
                raise ValueError(
                    "JWT audience mismatch: {!r} not in {!r}".format(audience, aud)
                )

        return payload

    def decode_without_verification(self, token):
        """Decode JWT payload without verifying signature. For inspection only."""
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format: expected 3 parts")
        return json.loads(_decode_base64url(parts[1]).decode("utf-8"))

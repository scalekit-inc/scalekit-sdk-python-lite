import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request
import urllib.error

try:
    from typing import Dict, Optional
except ImportError:
    pass

from scalekit._core import CoreClient, ScalekitError, _SDK_VERSION_HEADER, _USER_AGENT
from scalekit._jwt import JwtValidator
from scalekit.organization import OrganizationClient
from scalekit.user import UserClient
from scalekit.connection import ConnectionClient
from scalekit.directory import DirectoryClient

_WEBHOOK_TOLERANCE_SECONDS = 5 * 60


class ScalekitClient(object):
    """Unified Scalekit client. Instantiate once and reuse across your app."""

    def __init__(self, env_url, client_id, client_secret):
        self._core = CoreClient(env_url, client_id, client_secret)
        self._jwt = JwtValidator(self._core)
        self._organization = OrganizationClient(self._core)
        self._user = UserClient(self._core)
        self._connection = ConnectionClient(self._core)
        self._directory = DirectoryClient(self._core)

    @property
    def organization(self):
        return self._organization

    @property
    def user(self):
        return self._user

    @property
    def connection(self):
        return self._connection

    @property
    def directory(self):
        return self._directory

    def get_authorization_url(self, redirect_uri, options=None):
        """Build an authorization URL for the OAuth2 authorization code flow.

        options keys: connection_id, organization_id, domain, login_hint,
                      state, nonce, scope, code_challenge, code_challenge_method
        """
        if options is None:
            options = {}

        params = {
            "response_type": "code",
            "client_id": self._core.client_id,
            "redirect_uri": redirect_uri,
            "scope": options.get("scope", "openid profile email offline_access"),
        }

        optional_keys = [
            "connection_id",
            "organization_id",
            "domain",
            "login_hint",
            "state",
            "nonce",
            "code_challenge",
            "code_challenge_method",
        ]
        for key in optional_keys:
            if key in options and options[key] is not None:
                params[key] = options[key]

        base_url = "{}/oauth/authorize".format(self._core.env_url)
        return "{}?{}".format(base_url, urllib.parse.urlencode(params))

    def authenticate_with_code(self, code, redirect_uri, code_verifier=None):
        """Exchange an authorization code for tokens.

        Returns a dict with: user, id_token, access_token, refresh_token.
        """
        post_data = {
            "grant_type": "authorization_code",
            "client_id": self._core.client_id,
            "client_secret": self._core.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier is not None:
            post_data["code_verifier"] = code_verifier

        data = urllib.parse.urlencode(post_data).encode("utf-8")
        url = "{}/oauth/token".format(self._core.env_url)
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("x-sdk-version", _SDK_VERSION_HEADER)
        req.add_header("user-agent", _USER_AGENT)

        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                err = json.loads(raw)
            except ValueError:
                err = {}
            raise ScalekitError(
                exc.code,
                err.get("error_description", raw),
                err.get("error"),
            )

        id_token = body.get("id_token")
        user = {}
        if id_token:
            try:
                user = self._jwt.decode_without_verification(id_token)
            except Exception:
                pass

        return {
            "user": user,
            "id_token": id_token,
            "access_token": body.get("access_token"),
            "refresh_token": body.get("refresh_token"),
        }

    def validate_token(self, token, issuer=None, audience=None):
        """Validate an RS256 JWT and return its payload. Raises ValueError on failure."""
        return self._jwt.validate(token, issuer=issuer, audience=audience)

    def get_logout_url(self, id_token_hint=None, post_logout_redirect_uri=None):
        """Build an OIDC logout URL."""
        params = {}
        if id_token_hint is not None:
            params["id_token_hint"] = id_token_hint
        if post_logout_redirect_uri is not None:
            params["post_logout_redirect_uri"] = post_logout_redirect_uri

        base_url = "{}/oidc/logout".format(self._core.env_url)
        if params:
            return "{}?{}".format(base_url, urllib.parse.urlencode(params))
        return base_url

    def verify_webhook_payload(self, secret, headers, payload):
        """Verify a Scalekit webhook payload signature. Returns True or raises ScalekitError."""
        webhook_id = headers.get("webhook-id")
        webhook_timestamp = headers.get("webhook-timestamp")
        webhook_signature = headers.get("webhook-signature")

        if not all([webhook_id, webhook_timestamp, webhook_signature]):
            raise ScalekitError(400, "Missing required webhook headers")

        secret_parts = secret.split("_")
        if len(secret_parts) < 2:
            raise ScalekitError(400, "Invalid webhook secret format")

        try:
            secret_bytes = base64.b64decode(secret_parts[1])
        except Exception:
            raise ScalekitError(400, "Invalid webhook secret encoding")

        try:
            ts = float(webhook_timestamp)
        except ValueError:
            raise ScalekitError(400, "Invalid webhook timestamp")

        now = time.time()
        if ts < (now - _WEBHOOK_TOLERANCE_SECONDS):
            raise ScalekitError(400, "Webhook timestamp too old")
        if ts > (now + _WEBHOOK_TOLERANCE_SECONDS):
            raise ScalekitError(400, "Webhook timestamp too new")

        payload_str = payload if isinstance(payload, str) else payload.decode("utf-8")
        data = "{}.{}.{}".format(webhook_id, int(ts), payload_str)
        computed = hmac.new(secret_bytes, data.encode("utf-8"), hashlib.sha256).digest()
        computed_b64 = base64.b64encode(computed).decode("utf-8")

        for versioned_sig in webhook_signature.split(" "):
            parts = versioned_sig.split(",", 1)
            if len(parts) == 2 and parts[1].strip() == computed_b64:
                return True

        raise ScalekitError(400, "Webhook signature verification failed")

    def refresh_access_token(self, refresh_token):
        """Exchange a refresh token for a new access token. Returns dict with access_token and refresh_token."""
        post_data = {
            "grant_type": "refresh_token",
            "client_id": self._core.client_id,
            "client_secret": self._core.client_secret,
            "refresh_token": refresh_token,
        }
        data = urllib.parse.urlencode(post_data).encode("utf-8")
        url = "{}/oauth/token".format(self._core.env_url)
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("x-sdk-version", _SDK_VERSION_HEADER)
        req.add_header("user-agent", _USER_AGENT)

        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                err = json.loads(raw)
            except ValueError:
                err = {}
            raise ScalekitError(exc.code, err.get("error_description", raw), err.get("error"))

        return {
            "access_token": body.get("access_token"),
            "refresh_token": body.get("refresh_token"),
        }

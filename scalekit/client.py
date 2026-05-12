import base64
import hashlib
import hmac
import json
import time
import urllib.parse

import urllib3

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
    """Unified Scalekit client. Instantiate once and reuse across your application.

    Args:
        env_url:       Your Scalekit environment URL,
                       e.g. ``https://acme.scalekit.cloud``.
        client_id:     OAuth2 client ID (starts with ``skc_``).
        client_secret: OAuth2 client secret.
        timeout:       Per-request timeout in seconds. Defaults to 30.
        max_retries:   Number of retry attempts on transient errors (429, 5xx,
                       network failures). Defaults to 3.

    Example::

        from scalekit import ScalekitClient

        client = ScalekitClient(
            env_url="https://acme.scalekit.cloud",
            client_id="skc_...",
            client_secret="...",
        )
    """

    def __init__(self, env_url, client_id, client_secret,
                 connect_timeout=10, read_timeout=30, max_retries=3):
        self._core = CoreClient(env_url, client_id, client_secret,
                                connect_timeout=connect_timeout,
                                read_timeout=read_timeout,
                                max_retries=max_retries)
        self._jwt = JwtValidator(self._core)
        self._organization = OrganizationClient(self._core)
        self._user = UserClient(self._core)
        self._connection = ConnectionClient(self._core)
        self._directory = DirectoryClient(self._core)

    @property
    def organization(self):
        """Access organization management methods."""
        return self._organization

    @property
    def user(self):
        """Access user and membership management methods."""
        return self._user

    @property
    def connection(self):
        """Access SSO connection management methods."""
        return self._connection

    @property
    def directory(self):
        """Access SCIM directory management methods."""
        return self._directory

    def get_authorization_url(self, redirect_uri, options=None):
        """Build an authorization URL to start the OAuth2 / OIDC login flow.

        Redirect your end user to this URL. After they authenticate, Scalekit
        will redirect them back to ``redirect_uri`` with a ``?code=`` parameter.

        Args:
            redirect_uri: URL to redirect to after login. Must be whitelisted
                          in your Scalekit application settings.
            options:      Optional dict of additional parameters:

                          - ``connection_id`` — force a specific SSO connection
                          - ``organization_id`` — scope login to an organization
                          - ``domain`` — hint the IdP via domain
                          - ``login_hint`` — pre-fill the login email
                          - ``state`` — opaque value echoed back on redirect
                          - ``nonce`` — value included in the id_token claims
                          - ``scope`` — space-separated OIDC scopes (default:
                            ``"openid profile email offline_access"``)
                          - ``code_challenge`` — PKCE challenge
                          - ``code_challenge_method`` — PKCE method (e.g. ``"S256"``)

        Returns:
            Authorization URL string to redirect the user to.
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

        Call this from your redirect URI handler after the user is sent back
        from Scalekit with a ``?code=`` parameter.

        Args:
            code:           The authorization code from the query string.
            redirect_uri:   Must exactly match the URI used in
                            :meth:`get_authorization_url`.
            code_verifier:  PKCE verifier string (required if you used PKCE).

        Returns:
            Dict with the following keys:

            - ``access_token`` — bearer token for API calls on behalf of the user
            - ``id_token`` — JWT with user identity claims
            - ``refresh_token`` — long-lived token for refreshing the access token
            - ``user`` — decoded id_token payload as a dict (not signature-verified;
              call :meth:`validate_token` for verified claims)

        Raises:
            ScalekitError: If the code is invalid, expired, or the redirect URI
                           does not match.
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

        data = urllib.parse.urlencode(post_data)
        url = "{}/oauth/token".format(self._core.env_url)
        try:
            resp = self._core._http.request(
                "POST", url,
                body=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._core.timeout,
            )
        except urllib3.exceptions.MaxRetryError as exc:
            raise ScalekitError(0, "Token request failed: {}".format(exc.reason))

        from scalekit._core import _parse_response
        body = _parse_response(resp)

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
        """Validate an RS256 JWT and return its verified payload.

        Fetches Scalekit's public keys (JWKS) automatically and caches them
        for one hour. Verifies the signature, expiry, issuer, and audience.

        Args:
            token:    The JWT string to validate (typically an ``id_token``
                      or ``access_token`` issued by Scalekit).
            issuer:   Expected ``iss`` claim value. Defaults to your environment
                      URL if omitted (recommended to pass explicitly).
            audience: Expected ``aud`` claim value. Defaults to your client ID
                      if omitted.

        Returns:
            Dict of verified JWT claims.

        Raises:
            ValueError:     If the signature is invalid, the token is expired,
                            or the issuer/audience does not match.
            ScalekitError:  If the JWKS endpoint cannot be reached.
        """
        return self._jwt.validate(token, issuer=issuer, audience=audience)

    def refresh_access_token(self, refresh_token):
        """Exchange a refresh token for a new access token.

        Args:
            refresh_token: The ``refresh_token`` returned by a previous call to
                           :meth:`authenticate_with_code` or this method.

        Returns:
            Dict with ``access_token`` and ``refresh_token`` keys.

        Raises:
            ScalekitError: If the refresh token is invalid or expired.
        """
        post_data = {
            "grant_type": "refresh_token",
            "client_id": self._core.client_id,
            "client_secret": self._core.client_secret,
            "refresh_token": refresh_token,
        }
        data = urllib.parse.urlencode(post_data)
        url = "{}/oauth/token".format(self._core.env_url)
        try:
            resp = self._core._http.request(
                "POST", url,
                body=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self._core.timeout,
            )
        except urllib3.exceptions.MaxRetryError as exc:
            raise ScalekitError(0, "Token request failed: {}".format(exc.reason))

        from scalekit._core import _parse_response
        body = _parse_response(resp)

        return {
            "access_token": body.get("access_token"),
            "refresh_token": body.get("refresh_token"),
        }

    def get_logout_url(self, id_token_hint=None, post_logout_redirect_uri=None):
        """Build an OIDC logout URL.

        Redirect your end user to this URL to end their Scalekit session.

        Args:
            id_token_hint:            The user's current ``id_token`` (optional,
                                      but recommended so Scalekit can skip the
                                      confirmation prompt).
            post_logout_redirect_uri: URL to redirect to after logout completes.
                                      Must be whitelisted in your application settings.

        Returns:
            Logout URL string.
        """
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
        """Verify the HMAC-SHA256 signature on an incoming Scalekit webhook.

        Args:
            secret:  Webhook signing secret from the Scalekit dashboard.
                     Format: ``"whsec_<base64>"``.
            headers: Dict of HTTP request headers. Must include:

                     - ``webhook-id`` — unique message ID
                     - ``webhook-timestamp`` — Unix timestamp (seconds)
                     - ``webhook-signature`` — ``"v1,<base64_sig>"``

            payload: Raw request body string (do not parse it first).

        Returns:
            ``True`` if the signature is valid.

        Raises:
            ScalekitError: If the signature is invalid, the timestamp is outside
                           the ±5-minute tolerance window, or required headers
                           are missing.
        """
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

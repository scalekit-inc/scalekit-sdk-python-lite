import json
import platform
import time
import urllib.parse

import urllib3
from urllib3.util.retry import Retry
from urllib3.util.timeout import Timeout

try:
    from typing import Any, Dict, Optional
except ImportError:
    pass

_SDK_VERSION = "0.1.0"
_SDK_VERSION_HEADER = "Scalekit-Python-Lite/{}".format(_SDK_VERSION)
_USER_AGENT = "{} Python/{} ({})".format(
    _SDK_VERSION_HEADER,
    platform.python_version(),
    platform.platform(),
)

_DEFAULT_CONNECT_TIMEOUT = 10   # seconds to establish a connection
_DEFAULT_READ_TIMEOUT = 30      # seconds to wait for a response
_DEFAULT_MAX_RETRIES = 3        # retries on transient errors


def _make_pool_manager(max_retries):
    """Create a urllib3 PoolManager with retry and connection-pool settings."""
    retry = Retry(
        total=max_retries,
        backoff_factor=1,           # 1 s, 2 s, 4 s between retries
        status_forcelist={429, 500, 502, 503, 504},
        allowed_methods={"GET", "POST", "PATCH", "PUT", "DELETE"},
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    return urllib3.PoolManager(
        num_pools=2,
        maxsize=10,
        retries=retry,
    )


class ScalekitError(Exception):
    """Raised when the Scalekit API returns a 4xx or 5xx response.

    Attributes:
        status_code: HTTP status code returned by the API.
        message:     Human-readable error description.
        error_code:  Machine-readable error code from the API (may be None).
    """

    def __init__(self, status_code, message, error_code=None):
        super(ScalekitError, self).__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code

    def __repr__(self):
        return "ScalekitError(status_code={}, error_code={}, message={!r})".format(
            self.status_code, self.error_code, self.message
        )


class CoreClient(object):
    """Low-level HTTP client. Handles token acquisition, connection pooling,
    retries, and timeouts.

    Args:
        env_url:            Your Scalekit environment URL,
                            e.g. ``https://acme.scalekit.cloud``.
        client_id:          OAuth2 client ID (starts with ``skc_``).
        client_secret:      OAuth2 client secret.
        connect_timeout:    Seconds to wait when opening a connection (default: 10).
        read_timeout:       Seconds to wait for a response (default: 30).
        max_retries:        Retry attempts on transient errors (default: 3).
    """

    def __init__(self, env_url, client_id, client_secret,
                 connect_timeout=_DEFAULT_CONNECT_TIMEOUT,
                 read_timeout=_DEFAULT_READ_TIMEOUT,
                 max_retries=_DEFAULT_MAX_RETRIES):
        self.env_url = env_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = Timeout(connect=connect_timeout, read=read_timeout)
        self._http = _make_pool_manager(max_retries)
        self._token = None
        self._token_expires_at = 0

    def _get_token(self):
        """Return a valid M2M access token, fetching a new one only when near expiry."""
        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token

        data = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        })

        url = "{}/oauth/token".format(self.env_url)
        try:
            resp = self._http.request(
                "POST", url,
                body=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "x-sdk-version": _SDK_VERSION_HEADER,
                    "user-agent": _USER_AGENT,
                },
                timeout=self.timeout,
            )
        except urllib3.exceptions.MaxRetryError as exc:
            raise ScalekitError(0, "Token request failed: {}".format(exc.reason))

        body = _parse_response(resp)

        self._token = body["access_token"]
        expires_in = body.get("expires_in", 3600)
        # Refresh 60 s before actual expiry to avoid clock-edge failures.
        self._token_expires_at = now + expires_in - 60
        return self._token

    def _get_headers(self):
        """Build request headers including a fresh bearer token and SDK identifiers."""
        return {
            "Authorization": "Bearer {}".format(self._get_token()),
            "Content-Type": "application/json",
            "x-sdk-version": _SDK_VERSION_HEADER,
            "user-agent": _USER_AGENT,
        }

    def request(self, method, path, body=None, params=None):
        """Make an authenticated HTTP request and return parsed JSON.

        Connection pooling and retries are handled transparently by urllib3.
        Raises ``ScalekitError`` on permanent failures.

        Args:
            method: HTTP method string, e.g. ``"GET"``, ``"POST"``.
            path:   API path, e.g. ``"/api/v1/organizations"``.
            body:   Request body as a Python dict (JSON-serialised automatically).
            params: Query parameters as a dict; ``None`` values are dropped.

        Returns:
            Parsed JSON response as a dict, or ``{}`` for empty responses.

        Raises:
            ScalekitError: On 4xx/5xx responses or network-level failures.
        """
        url = "{}{}".format(self.env_url, path)
        if params:
            filtered = {k: v for k, v in params.items() if v is not None}
            if filtered:
                url = "{}?{}".format(url, urllib.parse.urlencode(filtered))

        encoded_body = None
        if body is not None:
            encoded_body = json.dumps(body).encode("utf-8")

        try:
            resp = self._http.request(
                method, url,
                body=encoded_body,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        except urllib3.exceptions.MaxRetryError as exc:
            raise ScalekitError(0, "Request failed: {}".format(exc.reason))

        return _parse_response(resp)


def _parse_response(resp):
    """Parse a urllib3 response, raising ScalekitError on 4xx/5xx."""
    raw = resp.data.decode("utf-8") if resp.data else ""

    if resp.status >= 400:
        try:
            err = json.loads(raw)
        except ValueError:
            err = {}
        raise ScalekitError(
            resp.status,
            err.get("message", err.get("error_description", raw)),
            err.get("code", err.get("error")),
        )

    return json.loads(raw) if raw else {}

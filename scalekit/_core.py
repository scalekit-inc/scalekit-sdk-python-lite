import json
import platform
import time
import urllib.request
import urllib.parse
import urllib.error

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

_DEFAULT_TIMEOUT = 30       # seconds per request
_DEFAULT_MAX_RETRIES = 3    # attempts after the first failure
_RETRY_BACKOFF = [1, 2, 4]  # seconds between retries (exponential)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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
    """Low-level HTTP client. Handles token acquisition, retries, and timeouts.

    Args:
        env_url:       Your Scalekit environment URL, e.g. https://acme.scalekit.cloud
        client_id:     OAuth2 client ID (starts with ``skc_``).
        client_secret: OAuth2 client secret.
        timeout:       Per-request timeout in seconds (default: 30).
        max_retries:   Number of retry attempts on transient errors (default: 3).
    """

    def __init__(self, env_url, client_id, client_secret,
                 timeout=_DEFAULT_TIMEOUT, max_retries=_DEFAULT_MAX_RETRIES):
        self.env_url = env_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.max_retries = max_retries
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
        }).encode("utf-8")

        url = "{}/oauth/token".format(self.env_url)
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("x-sdk-version", _SDK_VERSION_HEADER)
        req.add_header("user-agent", _USER_AGENT)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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
        except urllib.error.URLError as exc:
            raise ScalekitError(0, "Token request failed: {}".format(exc.reason))

        self._token = body["access_token"]
        expires_in = body.get("expires_in", 3600)
        # Refresh 60 s before actual expiry to avoid clock-edge failures.
        self._token_expires_at = now + expires_in - 60
        return self._token

    def _get_headers(self):
        """Build request headers including a fresh bearer token."""
        return {
            "Authorization": "Bearer {}".format(self._get_token()),
            "Content-Type": "application/json",
            "x-sdk-version": _SDK_VERSION_HEADER,
            "user-agent": _USER_AGENT,
        }

    def request(self, method, path, body=None, params=None):
        """Make an authenticated HTTP request and return parsed JSON.

        Retries automatically on transient errors (429, 5xx, network failures)
        with exponential backoff. Raises ``ScalekitError`` on permanent failures.

        Args:
            method: HTTP method string, e.g. ``"GET"``, ``"POST"``.
            path:   API path, e.g. ``"/api/v1/organizations"``.
            body:   Request body as a Python dict (JSON-serialised automatically).
            params: Query parameters as a dict; ``None`` values are dropped.

        Returns:
            Parsed JSON response as a dict, or ``{}`` for empty responses.

        Raises:
            ScalekitError: On 4xx/5xx responses after all retries are exhausted,
                           or on network-level failures.
        """
        url = "{}{}".format(self.env_url, path)
        if params:
            filtered = {k: v for k, v in params.items() if v is not None}
            if filtered:
                url = "{}?{}".format(url, urllib.parse.urlencode(filtered))

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        last_error = None
        attempts = 1 + self.max_retries

        for attempt in range(attempts):
            if attempt > 0:
                backoff = _RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)]
                time.sleep(backoff)

            try:
                headers = self._get_headers()
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw) if raw else {}

            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    # Respect Retry-After header if present.
                    retry_after = exc.headers.get("Retry-After")
                    if retry_after and attempt < attempts - 1:
                        try:
                            time.sleep(float(retry_after))
                        except ValueError:
                            pass
                    last_error = exc
                    continue

                if exc.code in _RETRYABLE_STATUS and attempt < attempts - 1:
                    last_error = exc
                    continue

                # Non-retryable HTTP error — raise immediately.
                raw = exc.read().decode("utf-8")
                try:
                    err = json.loads(raw)
                except ValueError:
                    err = {}
                raise ScalekitError(
                    exc.code,
                    err.get("message", raw),
                    err.get("code"),
                )

            except urllib.error.URLError as exc:
                # Network-level failure (DNS, connection refused, timeout).
                last_error = exc
                if attempt < attempts - 1:
                    continue
                raise ScalekitError(0, "Request failed: {}".format(exc.reason))

        # Exhausted retries on a retryable HTTP error.
        if isinstance(last_error, urllib.error.HTTPError):
            raw = last_error.read().decode("utf-8")
            try:
                err = json.loads(raw)
            except ValueError:
                err = {}
            raise ScalekitError(
                last_error.code,
                err.get("message", raw),
                err.get("code"),
            )

        raise ScalekitError(0, "Request failed after {} attempts".format(attempts))

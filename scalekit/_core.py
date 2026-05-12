import json
import platform
import sys
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


class ScalekitError(Exception):
    """Raised when Scalekit API returns a 4xx or 5xx response."""

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
    """Handles authentication and raw HTTP requests."""

    def __init__(self, env_url, client_id, client_secret):
        self.env_url = env_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._token = None
        self._token_expires_at = 0

    def _get_token(self):
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

        self._token = body["access_token"]
        expires_in = body.get("expires_in", 3600)
        self._token_expires_at = now + expires_in - 60
        return self._token

    def get_headers(self):
        return {
            "Authorization": "Bearer {}".format(self._get_token()),
            "Content-Type": "application/json",
            "x-sdk-version": _SDK_VERSION_HEADER,
            "user-agent": _USER_AGENT,
        }

    def request(self, method, path, body=None, params=None):
        """Make an authenticated HTTP request and return parsed JSON."""
        url = "{}{}".format(self.env_url, path)
        if params:
            filtered = {k: v for k, v in params.items() if v is not None}
            if filtered:
                url = "{}?{}".format(url, urllib.parse.urlencode(filtered))

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        headers = self.get_headers()
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode("utf-8")
                if raw:
                    return json.loads(raw)
                return {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                err = json.loads(raw)
            except ValueError:
                err = {}
            # Scalekit error body shape: {code, message, details:[]}
            raise ScalekitError(
                exc.code,
                err.get("message", raw),
                err.get("code"),
            )

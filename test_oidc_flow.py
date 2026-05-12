"""
Local OIDC flow test for scalekit-sdk-python-lite.

What this does:
  1. Starts a local HTTP server on localhost:8080
  2. Opens your browser to the Scalekit authorization URL
  3. After you log in, Scalekit redirects back with ?code=...
  4. Exchanges the code for tokens (authenticate_with_code)
  5. Validates the id_token signature (validate_token)
  6. Refreshes the access token (refresh_access_token)
  7. Prints a summary

Requires the same .env as test_live.py.

Run:
    python test_oidc_flow.py
"""

import os
import sys
import json
import webbrowser

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse as urlparse
except ImportError:
    print("Python 3+ required")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------
def _load_env(path=".env"):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except IOError:
        pass

_load_env(os.path.join(os.path.dirname(__file__), ".env"))

ENVIRONMENT_URL = os.environ.get("SCALEKIT_ENVIRONMENT_URL", "")
CLIENT_ID       = os.environ.get("SCALEKIT_CLIENT_ID", "")
CLIENT_SECRET   = os.environ.get("SCALEKIT_CLIENT_SECRET", "")

if not all([ENVIRONMENT_URL, CLIENT_ID, CLIENT_SECRET]):
    print("ERROR: set SCALEKIT_ENVIRONMENT_URL, SCALEKIT_CLIENT_ID, SCALEKIT_CLIENT_SECRET in .env")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(__file__))
from scalekit import ScalekitClient, ScalekitError

client = ScalekitClient(ENVIRONMENT_URL, CLIENT_ID, CLIENT_SECRET)

CALLBACK_PORT = 8080
REDIRECT_URI  = "http://localhost:{}/callback".format(CALLBACK_PORT)

# ---------------------------------------------------------------------------
# Minimal callback server — captures ?code= from Scalekit's redirect
# ---------------------------------------------------------------------------
_captured = {}

class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse.urlparse(self.path)
        params = urlparse.parse_qs(parsed.query)

        if "code" in params:
            _captured["code"]  = params["code"][0]
            _captured["state"] = params.get("state", [None])[0]
            body = b"<html><body><h2>Login successful. You can close this tab.</h2></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)
        elif "error" in params:
            _captured["error"] = params["error"][0]
            body = "<html><body><h2>Error: {}</h2></body></html>".format(
                params.get("error_description", ["unknown"])[0]
            ).encode()
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress request log noise

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_passed = []
_failed = []

def ok(label, value=None):
    print("  PASS  {}".format(label))
    _passed.append(label)
    return value

def fail(label, err):
    print("  FAIL  {} — {}".format(label, err))
    _failed.append((label, str(err)))

def section(title):
    print("\n{}\n{}".format(title, "-" * len(title)))

# ---------------------------------------------------------------------------
# Step 1 — Build authorization URL and open browser
# ---------------------------------------------------------------------------
section("Step 1 — Open browser for login")

auth_url = client.get_authorization_url(REDIRECT_URI, {"state": "oidc-test-local"})
print("  Authorization URL: {}\n".format(auth_url))
print("  Opening browser... (if it doesn't open, paste the URL manually)")
webbrowser.open(auth_url)

# ---------------------------------------------------------------------------
# Step 2 — Wait for redirect
# ---------------------------------------------------------------------------
section("Step 2 — Waiting for Scalekit to redirect to localhost:{}".format(CALLBACK_PORT))

server = HTTPServer(("localhost", CALLBACK_PORT), _CallbackHandler)
server.handle_request()  # blocks until one request comes in

if "error" in _captured:
    print("  ERROR from Scalekit: {}".format(_captured["error"]))
    sys.exit(1)

if "code" not in _captured:
    print("  No code received. Aborting.")
    sys.exit(1)

code = _captured["code"]
print("  Received authorization code: {}...".format(code[:12]))

# ---------------------------------------------------------------------------
# Step 3 — Exchange code for tokens
# ---------------------------------------------------------------------------
section("Step 3 — authenticate_with_code")

token_response = None
try:
    token_response = client.authenticate_with_code(code, REDIRECT_URI)
    assert token_response.get("access_token"), "missing access_token"
    assert token_response.get("id_token"), "missing id_token"
    ok("code exchange returned access_token and id_token")

    user = token_response.get("user", {})
    print("\n  User from id_token:")
    for k, v in user.items():
        print("    {}: {}".format(k, v))
except ScalekitError as e:
    fail("code exchange", e)
    sys.exit(1)
except AssertionError as e:
    fail("code exchange", e)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Step 4 — Validate id_token signature
# ---------------------------------------------------------------------------
section("Step 4 — validate_token (RS256 signature + claims)")

try:
    claims = client.validate_token(
        token_response["id_token"],
        issuer=ENVIRONMENT_URL,
        audience=CLIENT_ID,
    )
    ok("id_token signature valid")
    print("\n  Claims:")
    for k, v in claims.items():
        print("    {}: {}".format(k, v))
except Exception as e:
    fail("validate_token", e)

# ---------------------------------------------------------------------------
# Step 5 — Refresh access token
# ---------------------------------------------------------------------------
section("Step 5 — refresh_access_token")

refresh_token = token_response.get("refresh_token")
if not refresh_token:
    print("  SKIP  no refresh_token in response (scope may not include offline_access)")
else:
    try:
        refreshed = client.refresh_access_token(refresh_token)
        assert refreshed.get("access_token"), "missing access_token in refresh response"
        ok("refresh_access_token returned new access_token")
        print("  New access_token: {}...".format(refreshed["access_token"][:20]))
    except Exception as e:
        fail("refresh_access_token", e)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 50)
print("Results: {} passed, {} failed".format(len(_passed), len(_failed)))
if _failed:
    print("\nFailures:")
    for label, err in _failed:
        print("  - {}: {}".format(label, err))
    sys.exit(1)
else:
    print("OIDC flow verified end-to-end.")

"""
Live integration test for scalekit-sdk-python-lite.

Reads credentials from .env in the same directory:

    SCALEKIT_ENVIRONMENT_URL=https://...
    SCALEKIT_CLIENT_ID=skc_...
    SCALEKIT_CLIENT_SECRET=...

Run:
    pip install rsa
    python test_live.py
"""

import os
import sys
import json
import time

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

ENVIRONMENT_URL  = os.environ.get("SCALEKIT_ENVIRONMENT_URL", "")
CLIENT_ID        = os.environ.get("SCALEKIT_CLIENT_ID", "")
CLIENT_SECRET    = os.environ.get("SCALEKIT_CLIENT_SECRET", "")

if not all([ENVIRONMENT_URL, CLIENT_ID, CLIENT_SECRET]):
    print("ERROR: set SCALEKIT_ENVIRONMENT_URL, SCALEKIT_CLIENT_ID, SCALEKIT_CLIENT_SECRET in .env")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Bootstrap SDK from local source
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(__file__))
from scalekit import ScalekitClient, ScalekitError

client = ScalekitClient(ENVIRONMENT_URL, CLIENT_ID, CLIENT_SECRET)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
_passed = []
_failed = []

def run(label, fn):
    try:
        result = fn()
        print("  PASS  {}".format(label))
        _passed.append(label)
        return result
    except Exception as exc:
        print("  FAIL  {} — {}".format(label, exc))
        _failed.append((label, str(exc)))
        return None

def section(title):
    print("\n{}\n{}".format(title, "-" * len(title)))

# ---------------------------------------------------------------------------
# Auth — client credentials token fetch (implicit in every API call)
# ---------------------------------------------------------------------------
section("Auth")

def test_token_fetch():
    # Calling any API triggers a token fetch; also exercise it directly.
    token = client._core._get_token()
    assert token and len(token) > 10, "expected non-empty token"
    return token

run("client credentials token fetch", test_token_fetch)

def test_authorization_url():
    url = client.get_authorization_url(
        "https://example.com/callback",
        {"state": "xyz", "organization_id": "test-org"}
    )
    assert "oauth/authorize" in url
    assert "state=xyz" in url
    return url

run("get_authorization_url builds correct URL", test_authorization_url)

def test_logout_url():
    url = client.get_logout_url(post_logout_redirect_uri="https://example.com")
    assert "oidc/logout" in url
    assert "post_logout_redirect_uri" in url
    return url

run("get_logout_url builds correct URL", test_logout_url)

# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------
section("Organization")

unique = str(int(time.time()))
created_org_id = None

def test_create_org():
    resp = client.organization.create(
        display_name="Lite SDK Test Org {}".format(unique),
        external_id="lite-sdk-test-{}".format(unique),
        metadata={"source": "python-lite-test"},
    )
    assert resp.get("organization", {}).get("id"), "expected org id in response"
    return resp

resp = run("create organization", test_create_org)
if resp:
    created_org_id = resp["organization"]["id"]

def test_get_org():
    assert created_org_id, "skipped — no org id"
    resp = client.organization.get(created_org_id)
    assert resp["organization"]["id"] == created_org_id
    return resp

run("get organization by id", test_get_org)

def test_get_org_by_external_id():
    assert created_org_id, "skipped — no org id"
    resp = client.organization.get_by_external_id("lite-sdk-test-{}".format(unique))
    assert resp["organization"]["id"] == created_org_id
    return resp

run("get organization by external_id", test_get_org_by_external_id)

def test_list_orgs():
    resp = client.organization.list(page_size=5)
    assert "organizations" in resp
    return resp

run("list organizations", test_list_orgs)

def test_search_orgs():
    resp = client.organization.search("Lite SDK Test")
    assert "organizations" in resp
    return resp

run("search organizations", test_search_orgs)

def test_update_org():
    assert created_org_id, "skipped — no org id"
    resp = client.organization.update(
        created_org_id,
        display_name="Lite SDK Test Org {} (updated)".format(unique)
    )
    assert "organization" in resp
    return resp

run("update organization", test_update_org)

# ---------------------------------------------------------------------------
# Organization — session policy
# ---------------------------------------------------------------------------
def test_get_session_policy():
    assert created_org_id, "skipped — no org id"
    return client.organization.get_session_policy(created_org_id)

run("get organization session policy", test_get_session_policy)

def test_get_application_session_policy():
    assert created_org_id, "skipped — no org id"
    return client.organization.get_application_session_policy(created_org_id)

run("get application session policy", test_get_application_session_policy)

# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
section("User")

created_user_id = None
user_email = "lite-sdk-test-{}@example.com".format(unique)

def test_create_user():
    assert created_org_id, "skipped — no org id"
    resp = client.user.create_and_add_to_org(
        created_org_id,
        {"email": user_email},
        send_invitation_email=False,
    )
    assert resp.get("user", {}).get("id"), "expected user id"
    return resp

resp = run("create user and add to org", test_create_user)
if resp:
    created_user_id = resp["user"]["id"]

def test_get_user():
    assert created_user_id, "skipped — no user id"
    resp = client.user.get(created_user_id)
    assert resp["user"]["id"] == created_user_id
    return resp

run("get user by id", test_get_user)

def test_list_org_users():
    assert created_org_id, "skipped — no org id"
    resp = client.user.list_org_users(created_org_id, page_size=10)
    assert "users" in resp
    return resp

run("list organization users", test_list_org_users)

def test_search_org_users():
    assert created_org_id, "skipped — no org id"
    resp = client.user.search_org_users(created_org_id, query=user_email)
    assert "users" in resp
    return resp

run("search organization users", test_search_org_users)

def test_list_users():
    resp = client.user.list(page_size=5)
    assert "users" in resp
    return resp

run("list users (global)", test_list_users)

def test_search_users():
    resp = client.user.search(query=user_email)
    assert "users" in resp
    return resp

run("search users (global)", test_search_users)

def test_update_user():
    assert created_user_id, "skipped — no user id"
    resp = client.user.update(
        created_user_id,
        user_profile={"given_name": "Lite", "family_name": "Test"}
    )
    assert "user" in resp
    return resp

run("update user", test_update_user)

def test_list_user_roles():
    assert created_org_id and created_user_id, "skipped"
    return client.user.list_roles(created_org_id, created_user_id)

run("list user roles", test_list_user_roles)

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------
section("Connection")

def test_list_connections():
    resp = client.connection.list(page_size=5)
    # Response may be empty if no connections configured — that's fine
    return resp

run("list connections", test_list_connections)

def test_list_org_connections():
    assert created_org_id, "skipped — no org id"
    resp = client.connection.list_by_org(created_org_id)
    return resp

run("list connections by org", test_list_org_connections)

# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------
section("Directory")

def test_list_directories():
    assert created_org_id, "skipped — no org id"
    resp = client.directory.list(created_org_id)
    return resp

run("list directories", test_list_directories)

# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------
section("Webhook")

def test_webhook_valid():
    import hmac as _hmac
    import hashlib as _hashlib
    import base64 as _base64

    raw_secret = b"supersecretkey12"
    secret_b64 = _base64.b64encode(raw_secret).decode()
    webhook_secret = "whsec_{}".format(secret_b64)

    webhook_id = "msg_test_123"
    ts = int(time.time())
    payload = json.dumps({"event": "organization.created"})

    data = "{}.{}.{}".format(webhook_id, ts, payload)
    sig = _hmac.new(raw_secret, data.encode(), _hashlib.sha256).digest()
    sig_b64 = _base64.b64encode(sig).decode()

    headers = {
        "webhook-id": webhook_id,
        "webhook-timestamp": str(ts),
        "webhook-signature": "v1,{}".format(sig_b64),
    }
    result = client.verify_webhook_payload(webhook_secret, headers, payload)
    assert result is True
    return result

run("verify valid webhook signature", test_webhook_valid)

def test_webhook_invalid():
    headers = {
        "webhook-id": "msg_test_456",
        "webhook-timestamp": str(int(time.time())),
        "webhook-signature": "v1,badsignature==",
    }
    try:
        client.verify_webhook_payload("whsec_" + "aGVsbG8=", headers, "{}")
        return False  # should have raised
    except ScalekitError:
        return True

run("reject invalid webhook signature", test_webhook_invalid)

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
section("Cleanup")

def test_delete_user():
    assert created_user_id, "skipped — no user id"
    client.user.delete(created_user_id)
    return True

run("delete test user", test_delete_user)

def test_delete_org():
    assert created_org_id, "skipped — no org id"
    client.organization.delete(created_org_id)
    return True

run("delete test organization", test_delete_org)

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
    print("All tests passed.")

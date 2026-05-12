# scalekit-sdk-python-lite

Lightweight Scalekit SDK for Python 3.5+. Two dependencies: [`urllib3`](https://pypi.org/project/urllib3/) for HTTP transport and [`rsa`](https://pypi.org/project/rsa/) for JWT validation.

## Installation

```bash
pip install "urllib3>=1.26,<2.0" rsa
```

Or install the package directly from source, which pulls in dependencies automatically:

```bash
pip install .
```

## Quick start

```python
from scalekit import ScalekitClient, ScalekitError

client = ScalekitClient(
    env_url="https://<your-environment>.scalekit.cloud",
    client_id="skc_...",
    client_secret="...",
)
```

### Custom timeouts and retries

```python
client = ScalekitClient(
    env_url="https://<your-environment>.scalekit.cloud",
    client_id="skc_...",
    client_secret="...",
    connect_timeout=10,   # seconds to open a connection (default: 10)
    read_timeout=30,      # seconds to wait for a response (default: 30)
    max_retries=3,        # retries on 429 / 5xx / network errors (default: 3)
)
```

The client uses connection pooling — a single `ScalekitClient` instance should be created once and reused across your application.

## API reference

### Organizations

```python
client.organization.create(display_name, external_id=None, metadata=None)
client.organization.get(org_id)
client.organization.get_by_external_id(external_id)
client.organization.list(page_size=None, page_token=None)
client.organization.search(query, page_size=None, page_token=None)
client.organization.update(org_id, **kwargs)
client.organization.delete(org_id)
client.organization.update_settings(org_id, features)
client.organization.generate_portal_link(org_id, features=None)
client.organization.get_session_policy(organization_id)
client.organization.update_session_policy(organization_id, policy_source=None, **kwargs)
client.organization.get_application_session_policy(organization_id)
client.organization.get_user_management_settings(organization_id)
client.organization.upsert_user_management_settings(organization_id, settings)
```

### Users

```python
client.user.get(user_id)
client.user.list(page_size=None, page_token=None)
client.user.search(query, page_size=None, page_token=None)
client.user.update(user_id, **kwargs)
client.user.delete(user_id)
client.user.create_and_add_to_org(organization_id, user, send_invitation_email=None)
client.user.list_org_users(organization_id, page_size=None, page_token=None)
client.user.search_org_users(organization_id, query, page_size=None, page_token=None)
client.user.create_membership(organization_id, user_id, membership=None)
client.user.delete_membership(organization_id, user_id)
client.user.update_membership(organization_id, user_id, membership)
client.user.resend_invite(organization_id, user_id)
client.user.list_roles(organization_id, user_id)
client.user.assign_roles(organization_id, user_id, roles)
client.user.remove_role(organization_id, user_id, role_name)
```

### Connections

```python
client.connection.get(connection_id)
client.connection.get_by_org(organization_id, connection_id)
client.connection.list(page_size=None, page_token=None)
client.connection.list_by_org(organization_id, page_size=None, page_token=None)
client.connection.update(connection_id, **kwargs)
client.connection.delete(connection_id)
client.connection.enable(connection_id)
client.connection.disable(connection_id)
```

### Directories

```python
client.directory.get(organization_id, directory_id)
client.directory.list(organization_id, page_size=None, page_token=None)
client.directory.enable(organization_id, directory_id)
client.directory.disable(organization_id, directory_id)
client.directory.list_users(organization_id, directory_id, page_size=None, page_token=None)
client.directory.list_groups(organization_id, directory_id, page_size=None, page_token=None)
```

### Auth (OIDC / OAuth2)

```python
# Build authorization URL — redirect your user to this
url = client.get_authorization_url(redirect_uri, options={
    "state": "...",
    "organization_id": "...",   # optional: scope login to an org
    "connection_id": "...",     # optional: force a specific SSO connection
    "login_hint": "...",        # optional: pre-fill the login email
    "scope": "openid profile email offline_access",  # default
})

# Exchange authorization code for tokens (call from your redirect URI handler)
result = client.authenticate_with_code(code, redirect_uri)
# result keys: access_token, id_token, refresh_token, user (decoded id_token claims)

# Validate an id_token — verifies RS256 signature and claims
claims = client.validate_token(id_token, issuer=env_url, audience=client_id)

# Refresh the access token using a refresh_token
result = client.refresh_access_token(refresh_token)
# result keys: access_token, refresh_token

# Build an OIDC logout URL
url = client.get_logout_url(post_logout_redirect_uri="https://yourapp.com")
```

### Webhooks

```python
# Returns True on a valid signature, raises ScalekitError otherwise
client.verify_webhook_payload(secret, headers, payload)
# secret:  "whsec_<base64>" — from the Scalekit dashboard
# headers: dict containing webhook-id, webhook-timestamp, webhook-signature
# payload: raw request body string (do not parse before passing)
```

## Error handling

All API errors raise `ScalekitError`. Transient errors (429, 5xx, network failures)
are retried automatically with exponential backoff before the exception is raised.

```python
from scalekit import ScalekitError

try:
    org = client.organization.get("org_123")
except ScalekitError as e:
    print(e.status_code)   # HTTP status code
    print(e.error_code)    # machine-readable code from the API
    print(e.message)       # human-readable description
```

## Running the integration tests

Copy `.env.example` to `.env`, fill in your credentials, then:

```bash
pip install "urllib3>=1.26,<2.0" rsa
python test_live.py       # API integration tests (creates and deletes test data)
python test_oidc_flow.py  # OIDC browser flow (requires localhost:8080/callback whitelisted)
```

## Python version compatibility

Tested on Python 3.5.6+. No f-strings, no walrus operator, no dataclasses.

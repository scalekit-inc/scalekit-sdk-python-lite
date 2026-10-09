# B2B sample: per-organization branding

**Acme Projects** is a small B2B SaaS app. Each of its customers is a Scalekit
organization, and each one gets its own logo, colours and name on Scalekit's hosted
login, signup and admin portal pages. The app's own dashboard uses the same branding,
so a customer's users see one consistent brand from login onwards.

It shows how to:

| Step | SDK call |
|---|---|
| Give an organization its own branding | `client.organization.set_branding(org_id, settings)` |
| Read it (to theme your own UI) | `client.organization.get_branding(org_id)` |
| Switch back to the environment branding, keeping the saved one | `client.organization.use_environment_branding(org_id)` |
| Re-apply the saved branding | `client.organization.reapply_branding(org_id)` |
| Send a user to the organization's branded login or signup page | `client.get_authorization_url(redirect_uri, {"organization_id": org_id, "prompt": "create"})` |
| Finish sign-in | `client.authenticate_with_code(code, redirect_uri)` + `client.validate_token(id_token)` |

## 1. Configure Scalekit (once)

1. **Turn on Organization Branding** for your environment: dashboard → **Branding** →
   **Organization Branding** → Save. Without it the branding API returns 403.
2. On **Settings → API Credentials**:
   - copy your environment URL and client ID, and create a client secret;
   - under the redirect URLs, add `http://localhost:8080/callback` as an allowed callback URL
     and `http://localhost:8080/` as a post-logout URL.

## 2. Run it

```bash
cd examples/b2b-org-branding
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in the three SCALEKIT_* values
python seed.py              # creates two branded demo organizations
python app.py               # http://localhost:8080
```

`seed.py` creates **Wayne Enterprises** (dark, square corners) and **Umbrella Corp**
(red, with its own name "Umbrella Workspace") and prints each one's login URL. It is safe
to run again; it finds the organizations by `external_id`.

## 3. Try it

1. Open http://localhost:8080. Each organization is listed with its logo and whether it
   uses its own branding.
2. Click **Sign in** on Umbrella Corp. Scalekit's hosted login opens in Umbrella's red
   with its logo and "Login to Umbrella Workspace". **Sign up** opens the signup page
   with the same branding.
3. Sign in. You land on the app's dashboard, themed from the same branding.
4. Click **Branding** on an organization to change its colours, logo or name. **Save and apply**
   replaces what it had saved; blank fields fall back to your environment branding.
   **Use environment branding** switches it back (its own branding is kept) and
   **Re-apply saved branding** restores it. **Try the login page** shows the result.

## How the branding settings work

```python
client.organization.set_branding(org_id, {
    "portal_customization": {
        "logo_url": "https://cdn.example.com/logo.png",
        "icon_url": "https://cdn.example.com/favicon.ico",
        "button_color": "#B71C1C",
        "button_hover_color": "#8E1414",
        "login_bg_color": "#FDECEA",
        "border_radius": "lg",            # none | sm | md | lg
    },
    "application_customization": {
        "name": "Umbrella Workspace",     # optional; defaults to the organization's name
        "privacy_policy_url": "https://example.com/privacy",
        "terms_of_service_url": "https://example.com/terms",
    },
})
```

- `set_branding` **replaces** the organization's saved branding. Keys you leave out inherit
  the environment value; an empty string (`""`) removes the value for that organization.
- `get_branding` returns only what the organization overrides, not the merged result, plus
  `source` (`BRANDING_SOURCE_CUSTOM` or `BRANDING_SOURCE_ENVIRONMENT`).
- Setting an organization's logo with `organization.update(org_id, logo_url=...)` is the
  same as setting `portal_customization.logo_url`.
- The hosted pages use an organization's branding when the login is for that organization:
  pass `organization_id` to `get_authorization_url`.

The admin routes in `app.py` are unauthenticated to keep the sample short. Protect them with
your own admin checks in a real app.

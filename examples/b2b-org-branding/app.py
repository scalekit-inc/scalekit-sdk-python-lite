"""Acme Projects — a B2B SaaS sample showing per-organization branding with Scalekit.

Each of your customers is a Scalekit organization. This app:

* lists the organizations and lets their users sign in through Scalekit's hosted
  login page, which shows *that organization's* logo, colours and name;
* themes its own signed-in dashboard from the same branding;
* gives an admin page to edit an organization's branding, switch it back to the
  environment branding, or re-apply what it saved.

Run ``python seed.py`` once to create two branded demo organizations, then
``python app.py`` and open http://localhost:8080.
"""

import os
import re
import secrets
import sys

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # use the SDK from this repo
from scalekit import BRANDING_SOURCE_CUSTOM, ScalekitClient, ScalekitError  # noqa: E402

from settings import load_settings  # noqa: E402

config = load_settings()
scalekit_client = ScalekitClient(config["env_url"], config["client_id"], config["client_secret"])

app = Flask(__name__)
app.secret_key = config["session_secret"]

REDIRECT_URI = config["redirect_uri"]

# What the app falls back to when an organization has no branding of its own.
DEFAULT_THEME = {"name": "Acme Projects", "logo_url": "", "button_color": "#4F46E5", "background": "#F8FAFC"}

# The branding fields the admin form edits, as (form field, settings section, settings key).
BRANDING_FIELDS = [
    ("logo_url", "portal_customization", "logo_url"),
    ("icon_url", "portal_customization", "icon_url"),
    ("button_color", "portal_customization", "button_color"),
    ("button_hover_color", "portal_customization", "button_hover_color"),
    ("login_bg_color", "portal_customization", "login_bg_color"),
    ("border_radius", "portal_customization", "border_radius"),
    ("app_name", "application_customization", "name"),
    ("privacy_policy_url", "application_customization", "privacy_policy_url"),
    ("terms_of_service_url", "application_customization", "terms_of_service_url"),
]


def get_branding(org_id):
    """The organization's branding, or ``None`` when Organization Branding is turned off."""
    try:
        return scalekit_client.organization.get_branding(org_id).get("branding", {})
    except ScalekitError as exc:
        if exc.status_code == 403:
            return None
        raise


_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?$")


def _color(value, fallback):
    return value if value and _HEX_COLOR.match(value) else fallback


def _https_url(value, fallback):
    return value if value and value.startswith("https://") else fallback


def theme_for(org, branding):
    """Colours, logo and name for the app's own UI, taken from the organization's branding."""
    theme = dict(DEFAULT_THEME, name=org.get("display_name") or DEFAULT_THEME["name"])
    if branding and branding.get("source") == BRANDING_SOURCE_CUSTOM:
        settings = branding.get("customization_settings") or {}
        portal = settings.get("portal_customization") or {}
        application = settings.get("application_customization") or {}
        # Branding values are customer-entered: only use well-formed ones in the app's own styles.
        theme["logo_url"] = _https_url(portal.get("logo_url"), theme["logo_url"])
        theme["button_color"] = _color(portal.get("button_color"), theme["button_color"])
        theme["background"] = _color(portal.get("login_bg_color"), theme["background"])
        theme["name"] = application.get("name") or theme["name"]
    return theme


def list_organizations():
    return scalekit_client.organization.list(page_size=50).get("organizations", [])


def get_organization(org_id):
    try:
        return scalekit_client.organization.get(org_id)["organization"]
    except ScalekitError as exc:
        if exc.status_code == 404:
            abort(404)
        raise


# ---------------------------------------------------------------------------
# Sign in
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    rows = []
    for org in list_organizations():
        branding = get_branding(org["id"])
        rows.append({"org": org, "branding": branding, "theme": theme_for(org, branding)})
    enabled = all(row["branding"] is not None for row in rows)
    return render_template("home.html", rows=rows, branding_enabled=enabled, user=session.get("user"))


@app.route("/login/<org_id>")
def login(org_id):
    """Send the user to Scalekit's hosted login for one organization.

    ``organization_id`` scopes the login to that organization, which is also what
    makes the hosted page show the organization's branding.
    """
    state = secrets.token_urlsafe(24)
    session["oauth_state"] = state
    session["login_org_id"] = org_id
    options = {"organization_id": org_id, "state": state}
    if request.args.get("signup"):
        options["prompt"] = "create"
    return redirect(scalekit_client.get_authorization_url(REDIRECT_URI, options=options))


@app.route("/callback")
def callback():
    if request.args.get("error"):
        flash("Sign-in failed: {}".format(request.args.get("error_description") or request.args["error"]))
        return redirect(url_for("home"))
    if not request.args.get("state") or request.args.get("state") != session.pop("oauth_state", None):
        abort(400, "Invalid state")

    try:
        result = scalekit_client.authenticate_with_code(request.args["code"], REDIRECT_URI)
        claims = scalekit_client.validate_token(result["id_token"], issuer=config["issuer"])
    except (ScalekitError, ValueError) as exc:
        app.logger.error("Sign-in could not be completed: %s", exc)
        flash("Sign-in could not be completed: {}".format(exc))
        return redirect(url_for("home"))
    session["user"] = {
        "email": claims.get("email"),
        "name": claims.get("name") or claims.get("email"),
        "organization_id": claims.get("oid") or session.get("login_org_id"),
    }
    session["id_token"] = result["id_token"]
    return redirect(url_for("dashboard"))


@app.route("/app")
def dashboard():
    user = session.get("user")
    if not user:
        return redirect(url_for("home"))
    org = get_organization(user["organization_id"])
    return render_template("dashboard.html", user=user, org=org, theme=theme_for(org, get_branding(org["id"])))


@app.route("/logout")
def logout():
    id_token = session.get("id_token")
    session.clear()
    return redirect(scalekit_client.get_logout_url(
        id_token_hint=id_token, post_logout_redirect_uri=config["post_logout_redirect_uri"]))


# ---------------------------------------------------------------------------
# Admin: manage an organization's branding
# (protect these routes with your own admin authentication in a real app)
# ---------------------------------------------------------------------------

@app.route("/admin/orgs/<org_id>/branding", methods=["GET", "POST"])
def edit_branding(org_id):
    org = get_organization(org_id)
    try:
        if request.method == "POST":
            action = request.form.get("action", "save")
            if action == "save":
                scalekit_client.organization.set_branding(org_id, settings_from_form(request.form))
                flash("Saved. {} now uses its own branding.".format(org["display_name"]))
            elif action == "use_environment":
                scalekit_client.organization.use_environment_branding(org_id)
                flash("{} now uses the environment branding. Its own branding is kept.".format(org["display_name"]))
            elif action == "reapply":
                scalekit_client.organization.reapply_branding(org_id)
                flash("Re-applied {}'s saved branding.".format(org["display_name"]))
            return redirect(url_for("edit_branding", org_id=org_id))
    except ScalekitError as exc:
        flash("Scalekit rejected the change ({}): {}".format(exc.status_code, exc.message))

    branding = get_branding(org_id)
    if branding is None:
        return render_template("branding_disabled.html", org=org), 403
    return render_template("branding.html", org=org, branding=branding,
                           form=form_from_settings(branding.get("customization_settings") or {}))


def settings_from_form(form):
    """Build customization settings from the admin form. Blank fields are left out, so they
    inherit the environment value (send ``""`` instead to remove a value for this organization)."""
    settings = {}
    for field, section, key in BRANDING_FIELDS:
        value = (form.get(field) or "").strip()
        if value:
            settings.setdefault(section, {})[key] = value
    return settings


def form_from_settings(settings):
    return {field: (settings.get(section) or {}).get(key, "") for field, section, key in BRANDING_FIELDS}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=config["port"], debug=os.environ.get("FLASK_DEBUG") == "1")

"""Create (or update) two demo customer organizations, each with its own branding.

Safe to run more than once: organizations are found again by their external_id.

    python seed.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scalekit import ScalekitClient, ScalekitError  # noqa: E402

from settings import load_settings  # noqa: E402

DEMO_ORGANIZATIONS = [
    {
        "external_id": "demo-wayne-enterprises",
        "display_name": "Wayne Enterprises",
        "branding": {
            "portal_customization": {
                "logo_url": "https://logo.debounce.com/spotify.com",
                "button_color": "#111827",
                "button_hover_color": "#000000",
                "login_bg_color": "#F3F4F6",
                "border_radius": "none",
            },
            "application_customization": {
                "privacy_policy_url": "https://example.com/wayne/privacy",
                "terms_of_service_url": "https://example.com/wayne/terms",
            },
        },
    },
    {
        "external_id": "demo-umbrella-corp",
        "display_name": "Umbrella Corp",
        "branding": {
            "portal_customization": {
                "logo_url": "https://logo.debounce.com/netflix.com",
                "button_color": "#B71C1C",
                "button_hover_color": "#8E1414",
                "login_bg_color": "#FDECEA",
                "border_radius": "lg",
            },
            # A name set here wins over the organization's display name on the hosted pages.
            "application_customization": {"name": "Umbrella Workspace"},
        },
    },
]


def find_or_create(client, spec):
    try:
        return client.organization.get_by_external_id(spec["external_id"])["organization"]
    except ScalekitError as exc:
        if exc.status_code != 404:
            raise
    return client.organization.create(spec["display_name"], external_id=spec["external_id"])["organization"]


def main():
    config = load_settings()
    client = ScalekitClient(config["env_url"], config["client_id"], config["client_secret"])

    for spec in DEMO_ORGANIZATIONS:
        org = find_or_create(client, spec)
        try:
            branding = client.organization.set_branding(org["id"], spec["branding"])["branding"]
        except ScalekitError as exc:
            if exc.status_code == 403:
                sys.exit("Organization Branding is off for this environment. Turn it on in the "
                         "Scalekit dashboard (Branding > Organization Branding), then run this again.")
            raise
        print("{:<20} {}  source={}".format(org["display_name"], org["id"], branding["source"]))
        print("  login: {}".format(client.get_authorization_url(
            config["redirect_uri"], options={"organization_id": org["id"]})))


if __name__ == "__main__":
    main()

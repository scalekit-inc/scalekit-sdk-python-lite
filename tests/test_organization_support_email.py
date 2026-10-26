"""
Live integration tests for an organization's support email, set with the branding methods.

Uses only get_branding / set_branding / use_environment_branding / reapply_branding, as the
README shows. Each test checks what is saved and what the hosted login page shows for the
organization: it starts an authorization request with organization_id and reads the branding
the login page loads.

Reads credentials from .env in the repo root:

    SCALEKIT_ENVIRONMENT_URL=https://...
    SCALEKIT_CLIENT_ID=skc_...
    SCALEKIT_CLIENT_SECRET=...
    SCALEKIT_REDIRECT_URI=...         # a redirect URI allowed for that client
    SCALEKIT_ENV_SUPPORT_EMAIL=...    # the environment's support email (Branding page)

Organization Branding must be turned on for the environment. The tests are skipped when
any of these values is missing.

Run:
    python -m pytest tests/test_organization_support_email.py -v
"""

import json
import os
import sys
import time
import unittest
from urllib.parse import urljoin

import urllib3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scalekit import BRANDING_SOURCE_CUSTOM, BRANDING_SOURCE_ENVIRONMENT, ScalekitClient  # noqa: E402


def _load_env(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except IOError:
        pass


_load_env(os.path.join(os.path.dirname(__file__), '..', '.env'))

_REQUIRED = ("SCALEKIT_ENVIRONMENT_URL", "SCALEKIT_CLIENT_ID", "SCALEKIT_CLIENT_SECRET",
             "SCALEKIT_REDIRECT_URI", "SCALEKIT_ENV_SUPPORT_EMAIL")
_MISSING = [name for name in _REQUIRED if not os.environ.get(name)]

ENVIRONMENT_URL = os.environ.get("SCALEKIT_ENVIRONMENT_URL", "").rstrip("/")
CLIENT_ID = os.environ.get("SCALEKIT_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SCALEKIT_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("SCALEKIT_REDIRECT_URI", "")
ENV_SUPPORT_EMAIL = os.environ.get("SCALEKIT_ENV_SUPPORT_EMAIL", "")

ORG_EMAIL = "help@acme-support.dev"
SAVED = {
    "portal_customization": {"logo_url": "https://cdn.acme-support.dev/logo.png", "button_color": "#B71C1C"},
    "application_customization": {"privacy_policy_url": "https://acme-support.dev/privacy"},
}


def login_page_branding(organization_id=None):
    """Branding the hosted login page loads for a login to ``organization_id``."""
    http = urllib3.PoolManager()
    url = "{}/oauth/authorize?client_id={}&redirect_uri={}&response_type=code&scope=openid&state=s1".format(
        ENVIRONMENT_URL, CLIENT_ID, REDIRECT_URI)
    if organization_id:
        url += "&organization_id=" + organization_id
    # Follow the redirects to the hosted login page, keeping the cookies they set: the login
    # cookie (_auth) is what tells the backend which login, and so which organization, this is.
    jar = {}
    for _ in range(5):
        resp = http.request("GET", url, redirect=False,
                            headers={"Cookie": "; ".join("{}={}".format(k, v) for k, v in jar.items())})
        for c in resp.headers.getlist("Set-Cookie"):
            name, _, value = c.split(";", 1)[0].partition("=")
            jar[name] = value
        if resp.status not in (301, 302, 303, 307) or "/a/" in resp.headers.get("Location", ""):
            break
        url = urljoin(url, resp.headers["Location"])
    assert "_auth" in jar, "no login cookie; last response {} {}".format(resp.status, resp.headers.get("Location"))
    cookies = "; ".join("{}={}".format(k, v) for k, v in jar.items())
    resp = http.request("GET", ENVIRONMENT_URL + "/api/v1/auth:customizations", headers={"Cookie": cookies})
    assert resp.status == 200, "auth:customizations returned {}".format(resp.status)
    return json.loads(resp.data.decode("utf-8"))["customization_settings"]


def login_page_support_email(organization_id=None):
    return (login_page_branding(organization_id).get("application_customization") or {}).get("support_email", "")


@unittest.skipIf(_MISSING, "needs " + ", ".join(_MISSING))
class TestOrganizationSupportEmailWithSetBranding(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = ScalekitClient(ENVIRONMENT_URL, CLIENT_ID, CLIENT_SECRET)
        cls.unique = str(int(time.time()))
        # The login page without an organization shows the environment's support email.
        assert login_page_support_email() == ENV_SUPPORT_EMAIL, \
            "set the environment's support email to {} first".format(ENV_SUPPORT_EMAIL)

    def setUp(self):
        self.orgs = []
        self.org_id = self._org("Support Email Org")

    def tearDown(self):
        for org_id in self.orgs:
            try:
                self.client.organization.delete(org_id)
            except Exception:
                pass

    def _org(self, name):
        org_id = self.client.organization.create("{} {}".format(name, self.unique))["organization"]["id"]
        self.orgs.append(org_id)
        return org_id

    def _saved(self, org_id=None):
        return self.client.organization.get_branding(org_id or self.org_id)["branding"]

    def _set_support_email(self, org_id, email):
        """The read-merge-write a caller does to change only the support email."""
        branding = self.client.organization.get_branding(org_id)["branding"]
        settings = branding.get("customization_settings") or {}
        settings.setdefault("application_customization", {})["support_email"] = email
        return self.client.organization.set_branding(org_id, settings)

    # -- setting it ---------------------------------------------------------------

    def test_set_branding_with_only_the_support_email_shows_it_at_login(self):
        self.client.organization.set_branding(self.org_id, {
            "application_customization": {"support_email": ORG_EMAIL},
        })

        saved = self._saved()
        self.assertEqual(saved["source"], BRANDING_SOURCE_CUSTOM)
        self.assertEqual(saved["customization_settings"]["application_customization"]["support_email"], ORG_EMAIL)
        self.assertEqual(login_page_support_email(self.org_id), ORG_EMAIL)

    def test_set_branding_with_only_the_support_email_drops_the_other_saved_values(self):
        # The pitfall: set_branding replaces what was saved.
        self.client.organization.set_branding(self.org_id, SAVED)

        self.client.organization.set_branding(self.org_id, {
            "application_customization": {"support_email": ORG_EMAIL},
        })

        settings = self._saved()["customization_settings"]
        self.assertNotIn("portal_customization", settings)
        self.assertNotIn("privacy_policy_url", settings["application_customization"])
        page = login_page_branding(self.org_id)
        self.assertNotEqual(page["portal_customization"].get("logo_url"), SAVED["portal_customization"]["logo_url"])

    def test_read_merge_write_keeps_the_other_saved_values(self):
        self.client.organization.set_branding(self.org_id, SAVED)

        self._set_support_email(self.org_id, ORG_EMAIL)

        settings = self._saved()["customization_settings"]
        self.assertEqual(settings["portal_customization"], SAVED["portal_customization"])
        self.assertEqual(settings["application_customization"], {
            "privacy_policy_url": "https://acme-support.dev/privacy", "support_email": ORG_EMAIL})
        page = login_page_branding(self.org_id)
        self.assertEqual(page["application_customization"]["support_email"], ORG_EMAIL)
        self.assertEqual(page["portal_customization"]["logo_url"], SAVED["portal_customization"]["logo_url"])

    def test_changing_it_again_replaces_it(self):
        self._set_support_email(self.org_id, ORG_EMAIL)
        self._set_support_email(self.org_id, "new@acme-support.dev")

        self.assertEqual(login_page_support_email(self.org_id), "new@acme-support.dev")

    # -- falling back to the environment's ------------------------------------------------

    def test_custom_branding_without_the_key_shows_the_environment_support_email(self):
        self.client.organization.set_branding(self.org_id, SAVED)

        self.assertEqual(login_page_support_email(self.org_id), ENV_SUPPORT_EMAIL)

    def test_leaving_the_key_out_removes_it_and_brings_back_the_environment_support_email(self):
        self._set_support_email(self.org_id, ORG_EMAIL)

        # As in the README
        settings = self._saved().get("customization_settings") or {}
        settings.get("application_customization", {}).pop("support_email", None)
        self.client.organization.set_branding(self.org_id, settings)

        self.assertNotIn("support_email", self._saved()["customization_settings"]["application_customization"])
        self.assertEqual(login_page_support_email(self.org_id), ENV_SUPPORT_EMAIL)

    def test_an_empty_string_is_saved_and_shows_no_support_email(self):
        # The other pitfall: "" is the organization's own (empty) value, not "inherit".
        self._set_support_email(self.org_id, ORG_EMAIL)

        self._set_support_email(self.org_id, "")

        self.assertEqual(self._saved()["customization_settings"]["application_customization"]["support_email"], "")
        self.assertEqual(login_page_support_email(self.org_id), "")

    def test_environment_branding_shows_the_environment_support_email_and_keeps_the_saved_one(self):
        self._set_support_email(self.org_id, ORG_EMAIL)

        self.client.organization.use_environment_branding(self.org_id)

        saved = self._saved()
        self.assertEqual(saved["source"], BRANDING_SOURCE_ENVIRONMENT)
        self.assertEqual(saved["customization_settings"]["application_customization"]["support_email"], ORG_EMAIL)
        self.assertEqual(login_page_support_email(self.org_id), ENV_SUPPORT_EMAIL)

        self.client.organization.reapply_branding(self.org_id)
        self.assertEqual(login_page_support_email(self.org_id), ORG_EMAIL)

    # -- isolation -------------------------------------------------------------------------

    def test_another_organization_and_a_login_without_one_are_not_affected(self):
        other = self._org("Other Org")

        self._set_support_email(self.org_id, ORG_EMAIL)

        self.assertEqual(self._saved(other)["source"], BRANDING_SOURCE_ENVIRONMENT)
        self.assertEqual(login_page_support_email(other), ENV_SUPPORT_EMAIL)
        self.assertEqual(login_page_support_email(), ENV_SUPPORT_EMAIL)


if __name__ == "__main__":
    unittest.main()

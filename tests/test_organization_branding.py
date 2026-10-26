"""Unit tests for the organization branding methods. No network required.

The HTTP layer is replaced with a recorder, so these tests pin the exact method,
path and JSON body each call sends, and how API errors surface.
"""

import json
import unittest

from scalekit import BRANDING_SOURCE_CUSTOM, BRANDING_SOURCE_ENVIRONMENT, ScalekitError
from scalekit.client import ScalekitClient

ORG_ID = "org_59615193906282635"
PATH = "https://example.scalekit.cloud/api/v1/organizations/{}/portal_customizations".format(ORG_ID)

SETTINGS = {
    "portal_customization": {"logo_url": "https://cdn.acme.com/logo.png", "button_color": "#B71C1C"},
    "application_customization": {"name": "Acme Portal"},
}


class _Response(object):
    def __init__(self, status, body):
        self.status = status
        self.data = json.dumps(body).encode("utf-8") if body is not None else b""


class _RecordingHttp(object):
    """Stands in for urllib3.PoolManager: records each request, replays queued responses."""

    def __init__(self):
        self.calls = []
        self.responses = []

    def request(self, method, url, body=None, headers=None, timeout=None):
        self.calls.append({
            "method": method,
            "url": url,
            "body": json.loads(body.decode("utf-8")) if body else None,
            "headers": headers,
        })
        return self.responses.pop(0) if self.responses else _Response(200, {})


class TestOrganizationBranding(unittest.TestCase):
    def setUp(self):
        self.client = ScalekitClient(
            env_url="https://example.scalekit.cloud/",
            client_id="skc_test",
            client_secret="test_secret",
        )
        self.http = _RecordingHttp()
        self.client._core._http = self.http
        self.client._core._get_token = lambda: "token_123"

    def _respond(self, status, body):
        self.http.responses.append(_Response(status, body))

    def _only_call(self):
        self.assertEqual(len(self.http.calls), 1)
        return self.http.calls[0]

    # -- get_branding ---------------------------------------------------------

    def test_get_branding_reads_the_organization_endpoint(self):
        self._respond(200, {"branding": {"source": BRANDING_SOURCE_CUSTOM, "customization_settings": SETTINGS}})

        result = self.client.organization.get_branding(ORG_ID)

        call = self._only_call()
        self.assertEqual(call["method"], "GET")
        self.assertEqual(call["url"], PATH)
        self.assertIsNone(call["body"])
        self.assertEqual(call["headers"]["Authorization"], "Bearer token_123")
        self.assertEqual(result["branding"]["source"], BRANDING_SOURCE_CUSTOM)
        self.assertEqual(result["branding"]["customization_settings"], SETTINGS)

    def test_get_branding_when_turned_off_raises_403(self):
        self._respond(403, {"code": 7, "message": "organization branding is not enabled for this environment"})

        with self.assertRaises(ScalekitError) as ctx:
            self.client.organization.get_branding(ORG_ID)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("not enabled", ctx.exception.message)

    def test_get_branding_for_unknown_org_raises_404(self):
        self._respond(404, {"code": 5, "message": "organization not found"})

        with self.assertRaises(ScalekitError) as ctx:
            self.client.organization.get_branding("org_404")

        self.assertEqual(ctx.exception.status_code, 404)

    # -- set_branding -----------------------------------------------------------

    def test_set_branding_sends_custom_source_and_the_settings_verbatim(self):
        self._respond(200, {"branding": {"source": BRANDING_SOURCE_CUSTOM, "customization_settings": SETTINGS}})

        result = self.client.organization.set_branding(ORG_ID, SETTINGS)

        call = self._only_call()
        self.assertEqual(call["method"], "PUT")
        self.assertEqual(call["url"], PATH)
        self.assertEqual(call["body"], {"source": BRANDING_SOURCE_CUSTOM, "customization_settings": SETTINGS})
        self.assertEqual(result["branding"]["source"], BRANDING_SOURCE_CUSTOM)

    def test_set_branding_keeps_empty_strings_which_remove_a_value(self):
        # "" means "removed for this organization"; it must reach the API, not be dropped.
        settings = {"portal_customization": {"logo_url": "", "button_color": "#000000"}}

        self.client.organization.set_branding(ORG_ID, settings)

        self.assertEqual(self._only_call()["body"]["customization_settings"], settings)

    def test_set_branding_rejects_non_dict_settings_without_calling_the_api(self):
        for bad in (None, "", [], "logo"):
            with self.assertRaises(ValueError):
                self.client.organization.set_branding(ORG_ID, bad)
        self.assertEqual(self.http.calls, [])

    def test_set_branding_when_turned_off_raises_403_with_the_api_message(self):
        self._respond(403, {"code": 7, "message": "organization branding is not enabled for this environment"})

        with self.assertRaises(ScalekitError) as ctx:
            self.client.organization.set_branding(ORG_ID, SETTINGS)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.error_code, 7)

    # -- use_environment_branding / reapply_branding ------------------------------

    def test_use_environment_branding_sends_only_the_source(self):
        self.client.organization.use_environment_branding(ORG_ID)

        call = self._only_call()
        self.assertEqual(call["method"], "PUT")
        self.assertEqual(call["body"], {"source": BRANDING_SOURCE_ENVIRONMENT})

    def test_reapply_branding_sends_custom_without_settings(self):
        self.client.organization.reapply_branding(ORG_ID)

        self.assertEqual(self._only_call()["body"], {"source": BRANDING_SOURCE_CUSTOM})

    def test_reapply_with_nothing_saved_surfaces_400(self):
        self._respond(400, {"code": 9, "message": "no saved organization branding to re-apply"})

        with self.assertRaises(ScalekitError) as ctx:
            self.client.organization.reapply_branding(ORG_ID)

        self.assertEqual(ctx.exception.status_code, 400)

    # -- update_branding (general form) ---------------------------------------------

    def test_update_branding_accepts_short_source_names_in_any_case(self):
        for given, sent in (("custom", BRANDING_SOURCE_CUSTOM), ("CUSTOM", BRANDING_SOURCE_CUSTOM),
                            ("environment", BRANDING_SOURCE_ENVIRONMENT),
                            (BRANDING_SOURCE_ENVIRONMENT, BRANDING_SOURCE_ENVIRONMENT)):
            self.http.calls = []
            self.client.organization.update_branding(ORG_ID, given)
            self.assertEqual(self._only_call()["body"]["source"], sent)

    def test_update_branding_rejects_unknown_sources_without_calling_the_api(self):
        for bad in (None, "", "APPLICATION", "BRANDING_SOURCE_UNSPECIFIED"):
            with self.assertRaises(ValueError):
                self.client.organization.update_branding(ORG_ID, bad)
        self.assertEqual(self.http.calls, [])

    def test_update_branding_omits_settings_when_not_given(self):
        self.client.organization.update_branding(ORG_ID, "CUSTOM")

        self.assertNotIn("customization_settings", self._only_call()["body"])

    def test_each_organization_gets_its_own_path(self):
        self.client.organization.get_branding("org_1")
        self.client.organization.get_branding("org_2")

        urls = [c["url"] for c in self.http.calls]
        self.assertEqual(urls, [PATH.replace(ORG_ID, "org_1"), PATH.replace(ORG_ID, "org_2")])


class TestAuthorizationUrlForAnOrganization(unittest.TestCase):
    """The hosted login shows an organization's branding when the login is for that organization."""

    def setUp(self):
        self.client = ScalekitClient("https://example.scalekit.cloud", "skc_test", "secret")

    def _params(self, url):
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(url)
        self.assertEqual("{}://{}{}".format(parsed.scheme, parsed.netloc, parsed.path),
                         "https://example.scalekit.cloud/oauth/authorize")
        return {k: v[0] for k, v in parse_qs(parsed.query).items()}

    def test_organization_id_and_prompt_are_passed_through(self):
        params = self._params(self.client.get_authorization_url(
            "http://localhost:8080/callback",
            options={"organization_id": ORG_ID, "prompt": "create", "state": "s1"},
        ))
        self.assertEqual(params["organization_id"], ORG_ID)
        self.assertEqual(params["prompt"], "create")
        self.assertEqual(params["state"], "s1")
        self.assertEqual(params["client_id"], "skc_test")
        self.assertEqual(params["redirect_uri"], "http://localhost:8080/callback")

    def test_prompt_is_omitted_unless_given(self):
        params = self._params(self.client.get_authorization_url("http://localhost:8080/callback"))
        self.assertNotIn("prompt", params)
        self.assertNotIn("organization_id", params)


if __name__ == "__main__":
    unittest.main()

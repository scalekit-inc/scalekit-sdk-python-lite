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


class TestOrganizationSupportEmail(unittest.TestCase):
    """set/remove/get_support_email read the saved branding and change only the support email."""

    def setUp(self):
        self.client = ScalekitClient("https://example.scalekit.cloud/", "skc_test", "test_secret")
        self.http = _RecordingHttp()
        self.client._core._http = self.http
        self.client._core._get_token = lambda: "token_123"

    def _saved(self, source, settings):
        branding = {"source": source}
        if settings is not None:
            branding["customization_settings"] = settings
        self.http.responses.append(_Response(200, {"branding": branding}))

    def _put_body(self):
        self.assertEqual([c["method"] for c in self.http.calls], ["GET", "PUT"])
        self.assertEqual(self.http.calls[1]["url"], PATH)
        return self.http.calls[1]["body"]

    # -- set_support_email ------------------------------------------------------

    def test_set_keeps_the_saved_branding_and_adds_the_support_email(self):
        self._saved(BRANDING_SOURCE_CUSTOM, SETTINGS)

        self.client.organization.set_support_email(ORG_ID, "support@acme.com")

        body = self._put_body()
        self.assertEqual(body["source"], BRANDING_SOURCE_CUSTOM)
        self.assertEqual(body["customization_settings"], {
            "portal_customization": SETTINGS["portal_customization"],
            "application_customization": {"name": "Acme Portal", "support_email": "support@acme.com"},
        })

    def test_set_replaces_an_existing_support_email(self):
        self._saved(BRANDING_SOURCE_CUSTOM, {"application_customization": {"support_email": "old@acme.com"}})

        self.client.organization.set_support_email(ORG_ID, "new@acme.com")

        self.assertEqual(self._put_body()["customization_settings"],
                         {"application_customization": {"support_email": "new@acme.com"}})

    def test_set_with_nothing_saved_sends_only_the_support_email(self):
        self._saved(BRANDING_SOURCE_ENVIRONMENT, None)

        self.client.organization.set_support_email(ORG_ID, "support@acme.com")

        self.assertEqual(self._put_body(), {
            "source": BRANDING_SOURCE_CUSTOM,
            "customization_settings": {"application_customization": {"support_email": "support@acme.com"}},
        })

    def test_set_on_environment_branding_reapplies_what_was_saved(self):
        self._saved(BRANDING_SOURCE_ENVIRONMENT, SETTINGS)

        self.client.organization.set_support_email(ORG_ID, "support@acme.com")

        body = self._put_body()
        self.assertEqual(body["source"], BRANDING_SOURCE_CUSTOM)
        self.assertEqual(body["customization_settings"]["portal_customization"], SETTINGS["portal_customization"])

    def test_set_writes_the_current_shape_where_the_api_reads_it(self):
        # With placeholder_mappings saved, the API ignores application_customization.support_email.
        saved = {
            "placeholder_mappings": {"app_name": "Acme"},
            "theme": {"button_color": "#B71C1C"},
            "application_customization": {"privacy_policy_url": "https://acme.com/privacy"},
        }
        self._saved(BRANDING_SOURCE_CUSTOM, saved)

        self.client.organization.set_support_email(ORG_ID, "support@acme.com")

        sent = self._put_body()["customization_settings"]
        self.assertEqual(sent["placeholder_mappings"], {"app_name": "Acme", "app_support_email": "support@acme.com"})
        self.assertEqual(sent["application_customization"], saved["application_customization"])
        self.assertEqual(sent["theme"], saved["theme"])

    def test_set_does_not_mutate_the_response_it_read(self):
        saved = {"application_customization": {"name": "Acme"}}
        self._saved(BRANDING_SOURCE_CUSTOM, saved)

        self.client.organization.set_support_email(ORG_ID, "support@acme.com")

        self.assertEqual(saved, {"application_customization": {"name": "Acme"}})

    def test_set_strips_surrounding_spaces(self):
        self._saved(BRANDING_SOURCE_CUSTOM, {})

        self.client.organization.set_support_email(ORG_ID, "  support@acme.com ")

        self.assertEqual(self._put_body()["customization_settings"]["application_customization"]["support_email"],
                         "support@acme.com")

    def test_set_rejects_values_that_are_not_an_email_without_calling_the_api(self):
        for bad in (None, "", "   ", "support", "@acme.com", "support@", "sup port@acme.com", 42, ["a@b.c"]):
            with self.assertRaises(ValueError):
                self.client.organization.set_support_email(ORG_ID, bad)
        self.assertEqual(self.http.calls, [])

    def test_set_surfaces_an_api_rejection(self):
        self._saved(BRANDING_SOURCE_ENVIRONMENT, None)
        self.http.responses.append(_Response(400, {"code": 3, "message": "missing required key: theme"}))

        with self.assertRaises(ScalekitError) as ctx:
            self.client.organization.set_support_email(ORG_ID, "support@acme.com")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("missing required key", ctx.exception.message)

    def test_set_when_turned_off_raises_403_before_writing(self):
        self.http.responses.append(_Response(403, {"code": 7, "message": "organization branding is not enabled"}))

        with self.assertRaises(ScalekitError) as ctx:
            self.client.organization.set_support_email(ORG_ID, "support@acme.com")

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual([c["method"] for c in self.http.calls], ["GET"])

    # -- remove_support_email ---------------------------------------------------------

    def test_remove_drops_the_key_instead_of_sending_an_empty_string(self):
        self._saved(BRANDING_SOURCE_CUSTOM,
                    {"application_customization": {"name": "Acme", "support_email": "support@acme.com"}})

        self.client.organization.remove_support_email(ORG_ID)

        self.assertEqual(self._put_body(), {
            "source": BRANDING_SOURCE_CUSTOM,
            "customization_settings": {"application_customization": {"name": "Acme"}},
        })

    def test_remove_from_the_current_shape(self):
        self._saved(BRANDING_SOURCE_CUSTOM,
                    {"placeholder_mappings": {"app_name": "Acme", "app_support_email": "support@acme.com"}})

        self.client.organization.remove_support_email(ORG_ID)

        self.assertEqual(self._put_body()["customization_settings"], {"placeholder_mappings": {"app_name": "Acme"}})

    def test_remove_writes_nothing_when_no_support_email_is_set(self):
        self._saved(BRANDING_SOURCE_CUSTOM, SETTINGS)

        result = self.client.organization.remove_support_email(ORG_ID)

        self.assertEqual([c["method"] for c in self.http.calls], ["GET"])
        self.assertEqual(result["branding"]["customization_settings"], SETTINGS)

    def test_remove_on_environment_branding_writes_nothing(self):
        # Writing would switch the organization to custom branding.
        self._saved(BRANDING_SOURCE_ENVIRONMENT, {"application_customization": {"support_email": "support@acme.com"}})

        result = self.client.organization.remove_support_email(ORG_ID)

        self.assertEqual([c["method"] for c in self.http.calls], ["GET"])
        self.assertEqual(result["branding"]["source"], BRANDING_SOURCE_ENVIRONMENT)

    # -- get_support_email ----------------------------------------------------------

    def test_get_returns_the_saved_support_email(self):
        for saved in ({"application_customization": {"support_email": "support@acme.com"}},
                      {"placeholder_mappings": {"app_support_email": "support@acme.com"}}):
            self._saved(BRANDING_SOURCE_CUSTOM, saved)
            self.assertEqual(self.client.organization.get_support_email(ORG_ID), "support@acme.com")

    def test_get_returns_none_when_the_environment_support_email_applies(self):
        cases = (
            (BRANDING_SOURCE_CUSTOM, SETTINGS),                    # custom, no support email
            (BRANDING_SOURCE_CUSTOM, {"application_customization": {"support_email": ""}}),
            (BRANDING_SOURCE_ENVIRONMENT, {"application_customization": {"support_email": "old@acme.com"}}),
            (BRANDING_SOURCE_ENVIRONMENT, None),                   # nothing saved
        )
        for source, saved in cases:
            self._saved(source, saved)
            self.assertIsNone(self.client.organization.get_support_email(ORG_ID), (source, saved))

    def test_each_organization_is_read_and_written_on_its_own_path(self):
        self._saved(BRANDING_SOURCE_CUSTOM, {})

        self.client.organization.set_support_email("org_2", "support@acme.com")

        self.assertEqual({c["url"] for c in self.http.calls}, {PATH.replace(ORG_ID, "org_2")})


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

try:
    from typing import Any, Dict, List, Optional
except ImportError:
    pass


class OrganizationClient(object):

    def __init__(self, core):
        self._core = core

    def create(self, display_name, external_id=None, metadata=None):
        body = {"display_name": display_name}
        if external_id is not None:
            body["external_id"] = external_id
        if metadata is not None:
            body["metadata"] = metadata
        return self._core.request("POST", "/api/v1/organizations", body=body)

    def get(self, org_id):
        return self._core.request("GET", "/api/v1/organizations/{}".format(org_id))

    def get_by_external_id(self, external_id):
        return self._core.request("GET", "/api/v1/organizations:external/{}".format(external_id))

    def list(self, page_size=None, page_token=None):
        return self._core.request(
            "GET", "/api/v1/organizations",
            params={"page_size": page_size, "page_token": page_token},
        )

    def update(self, org_id, **kwargs):
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}".format(org_id), body=kwargs
        )

    def delete(self, org_id):
        return self._core.request("DELETE", "/api/v1/organizations/{}".format(org_id))

    def search(self, query, page_size=None, page_token=None):
        return self._core.request(
            "GET", "/api/v1/organizations:search",
            params={"query": query, "page_size": page_size, "page_token": page_token},
        )

    def update_settings(self, org_id, features):
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/settings".format(org_id),
            body={"features": features},
        )

    def generate_portal_link(self, org_id, features=None):
        return self._core.request(
            "PUT", "/api/v1/organizations/{}/portal_links".format(org_id),
            body={"features": features or []},
        )

    def get_session_policy(self, organization_id):
        return self._core.request(
            "GET", "/api/v1/organizations/{}/session-policy".format(organization_id)
        )

    def update_session_policy(self, organization_id, policy_source=None, **kwargs):
        body = {}
        if policy_source is not None:
            body["policy_source"] = policy_source
        body.update(kwargs)
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/session-policy".format(organization_id),
            body=body,
        )

    def get_application_session_policy(self, organization_id):
        return self._core.request(
            "GET", "/api/v1/organizations/{}/application-session-policy".format(organization_id)
        )

    def get_user_management_settings(self, organization_id):
        return self._core.request(
            "GET", "/api/v1/organizations/{}/settings/usermanagement".format(organization_id)
        )

    def upsert_user_management_settings(self, organization_id, settings):
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/settings/usermanagement".format(organization_id),
            body={"settings": settings},
        )

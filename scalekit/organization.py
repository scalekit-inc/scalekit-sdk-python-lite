try:
    from typing import Any, Dict, List, Optional
except ImportError:
    pass


class OrganizationClient(object):
    """Manage organizations in your Scalekit environment."""

    def __init__(self, core):
        self._core = core

    def create(self, display_name, external_id=None, metadata=None, logo_url=None, slug=None):
        """Create a new organization.

        Args:
            display_name: Human-readable name shown in the Scalekit dashboard.
            external_id:  Your own identifier for this organization (optional).
            metadata:     Arbitrary key/value dict to attach to the organization (optional).
            logo_url:     Publicly accessible URL of the organization's logo (optional).
                          Used for organization logo branding on hosted pages.
            slug:         DNS-safe slug for the organization, e.g. ``"acme"`` or
                          ``"app.acmecorp.com"`` (optional). Used to expand ``{{slug}}``
                          in template redirect URIs.

        Returns:
            Dict with an ``organization`` key containing the created organization.
        """
        body = {"display_name": display_name}
        if external_id is not None:
            body["external_id"] = external_id
        if metadata is not None:
            body["metadata"] = metadata
        if logo_url is not None:
            body["logo_url"] = logo_url
        if slug is not None:
            body["slug"] = slug
        return self._core.request("POST", "/api/v1/organizations", body=body)

    def get(self, org_id):
        """Fetch an organization by its Scalekit ID.

        Args:
            org_id: Scalekit organization ID (e.g. ``org_123...``).

        Returns:
            Dict with an ``organization`` key.
        """
        return self._core.request("GET", "/api/v1/organizations/{}".format(org_id))

    def get_by_external_id(self, external_id):
        """Fetch an organization by the external ID you assigned it.

        Args:
            external_id: The ``external_id`` value set when creating the organization.

        Returns:
            Dict with an ``organization`` key.
        """
        return self._core.request("GET", "/api/v1/organizations:external/{}".format(external_id))

    def list(self, page_size=None, page_token=None):
        """List all organizations in the environment, with optional pagination.

        Args:
            page_size:  Maximum number of results per page.
            page_token: Opaque token returned by a previous call to fetch the next page.

        Returns:
            Dict with an ``organizations`` list and optional ``next_page_token``.
        """
        return self._core.request(
            "GET", "/api/v1/organizations",
            params={"page_size": page_size, "page_token": page_token},
        )

    def update(self, org_id, **kwargs):
        """Update fields on an existing organization.

        Pass any writable organization fields as keyword arguments, e.g.
        ``display_name="Acme Corp"``.

        Args:
            org_id:   Scalekit organization ID.
            **kwargs: Fields to update.

        Returns:
            Dict with the updated ``organization``.
        """
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}".format(org_id), body=kwargs
        )

    def delete(self, org_id):
        """Permanently delete an organization and all its data.

        Args:
            org_id: Scalekit organization ID.

        Returns:
            Empty dict on success.
        """
        return self._core.request("DELETE", "/api/v1/organizations/{}".format(org_id))

    def search(self, query, page_size=None, page_token=None):
        """Search organizations by name or external ID.

        Args:
            query:      Search string.
            page_size:  Maximum results per page.
            page_token: Pagination token from a previous response.

        Returns:
            Dict with an ``organizations`` list.
        """
        return self._core.request(
            "GET", "/api/v1/organizations:search",
            params={"query": query, "page_size": page_size, "page_token": page_token},
        )

    def update_settings(self, org_id, features):
        """Update feature settings for an organization.

        Args:
            org_id:   Scalekit organization ID.
            features: List of feature objects to enable or configure.

        Returns:
            Dict with the updated settings.
        """
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/settings".format(org_id),
            body={"features": features},
        )

    def generate_portal_link(self, org_id, features=None):
        """Generate a self-service admin portal link for an organization.

        Args:
            org_id:   Scalekit organization ID.
            features: List of portal feature strings to enable (optional).

        Returns:
            Dict containing the portal ``link`` URL.
        """
        return self._core.request(
            "PUT", "/api/v1/organizations/{}/portal_links".format(org_id),
            body={"features": features or []},
        )

    def get_session_policy(self, organization_id):
        """Retrieve the session policy configured for an organization.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            Dict containing the session policy settings.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/session-policy".format(organization_id)
        )

    def update_session_policy(self, organization_id, policy_source=None, **kwargs):
        """Update the session policy for an organization.

        Args:
            organization_id: Scalekit organization ID.
            policy_source:   Policy source type (e.g. ``"CUSTOM"`` or ``"APPLICATION"``).
            **kwargs:        Additional policy fields such as ``absolute_session_timeout``
                             or ``idle_session_timeout``.

        Returns:
            Dict with the updated session policy.
        """
        body = {}
        if policy_source is not None:
            body["policy_source"] = policy_source
        body.update(kwargs)
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/session-policy".format(organization_id),
            body=body,
        )

    def get_application_session_policy(self, organization_id):
        """Retrieve the application-level session policy that applies to an organization.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            Dict containing the application session policy.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/application-session-policy".format(organization_id)
        )

    def get_user_management_settings(self, organization_id):
        """Retrieve user management settings for an organization.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            Dict containing user management settings.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/settings/usermanagement".format(organization_id)
        )

    def upsert_user_management_settings(self, organization_id, settings):
        """Create or update user management settings for an organization.

        Args:
            organization_id: Scalekit organization ID.
            settings:        Dict of user management settings to apply.

        Returns:
            Dict with the updated settings.
        """
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/settings/usermanagement".format(organization_id),
            body={"settings": settings},
        )

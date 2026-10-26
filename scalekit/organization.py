import copy

try:
    from typing import Any, Dict, List, Optional
except ImportError:
    pass


#: The organization inherits the environment branding.
BRANDING_SOURCE_ENVIRONMENT = "BRANDING_SOURCE_ENVIRONMENT"
#: The organization's own branding is applied over the environment branding.
BRANDING_SOURCE_CUSTOM = "BRANDING_SOURCE_CUSTOM"

_BRANDING_SOURCES = {
    "ENVIRONMENT": BRANDING_SOURCE_ENVIRONMENT,
    "CUSTOM": BRANDING_SOURCE_CUSTOM,
    BRANDING_SOURCE_ENVIRONMENT: BRANDING_SOURCE_ENVIRONMENT,
    BRANDING_SOURCE_CUSTOM: BRANDING_SOURCE_CUSTOM,
}


def _branding_source(source):
    """Normalise ``"CUSTOM"`` / ``"ENVIRONMENT"`` (any case) to the API's enum value."""
    normalised = _BRANDING_SOURCES.get(str(source).upper()) if source is not None else None
    if normalised is None:
        raise ValueError(
            "source must be {!r} or {!r}, got {!r}".format(
                BRANDING_SOURCE_CUSTOM, BRANDING_SOURCE_ENVIRONMENT, source
            )
        )
    return normalised


def _support_email_location(settings):
    """Return the (section, key) that holds the support email in ``settings``.

    Branding is saved in one of two shapes. Settings that have a
    ``placeholder_mappings`` section keep the support email there, as
    ``app_support_email``; the API reads ``application_customization`` only
    from settings without it.
    """
    if "placeholder_mappings" in settings:
        return "placeholder_mappings", "app_support_email"
    return "application_customization", "support_email"


def _saved_settings(branding_response):
    """Return the ``branding`` dict and a copy of its saved settings (``{}`` when none)."""
    branding = (branding_response or {}).get("branding") or {}
    settings = copy.deepcopy(branding.get("customization_settings") or {})
    return branding, settings


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
                          The logo is part of the organization's branding: with
                          organization branding turned on, setting it switches the
                          organization to custom branding (see :meth:`get_branding`).
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

    def update(self, org_id, display_name=None, external_id=None, metadata=None, logo_url=None, slug=None, **kwargs):
        """Update fields on an existing organization.

        Args:
            org_id:       Scalekit organization ID.
            display_name: New human-readable name for the organization (optional).
            external_id:  New external ID to map to your system (optional).
            metadata:     Key/value dict to attach to the organization (optional).
            logo_url:     Publicly accessible URL of the organization's logo (optional).
                          The logo is part of the organization's branding: with
                          organization branding turned on, setting it switches the
                          organization to custom branding (see :meth:`get_branding`).
            slug:         DNS-safe slug, e.g. ``"acme"`` or ``"app.acmecorp.com"`` (optional).
                          Expands ``{{slug}}`` in template redirect URIs.
            **kwargs:     Any additional writable organization fields.

        Returns:
            Dict with the updated ``organization``.
        """
        body = {}
        if display_name is not None:
            body["display_name"] = display_name
        if external_id is not None:
            body["external_id"] = external_id
        if metadata is not None:
            body["metadata"] = metadata
        if logo_url is not None:
            body["logo_url"] = logo_url
        if slug is not None:
            body["slug"] = slug
        body.update(kwargs)
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}".format(org_id), body=body
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

    # -----------------------------------------------------------------------
    # Organization branding
    #
    # Gives an organization its own look on the hosted login pages and the
    # admin portal. Organization branding must be turned on for the
    # environment first (dashboard: Branding > Organization Branding);
    # until then these calls raise ScalekitError with status_code 403.
    # -----------------------------------------------------------------------

    def get_branding(self, organization_id):
        """Retrieve an organization's branding.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            Dict with a ``branding`` key containing:

            - ``source`` — ``"BRANDING_SOURCE_CUSTOM"`` when the organization's
              own branding is applied, ``"BRANDING_SOURCE_ENVIRONMENT"`` when it
              inherits the environment branding.
            - ``customization_settings`` — the organization's saved settings, in
              the same shape as the environment branding (for example
              ``{"portal_customization": {"logo_url": ..., "button_color": ...},
              "application_customization": {"name": ...}}``). Returned for both
              sources, so saved branding can be re-applied later. Holds only
              what the organization overrides, not the merged result.
            - ``update_time`` — when the branding was last saved (absent when
              nothing has been saved).

        Raises:
            ScalekitError: 403 if organization branding is not turned on for
                           the environment, 404 if the organization does not exist.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/portal_customizations".format(organization_id)
        )

    def update_branding(self, organization_id, source, customization_settings=None):
        """Set an organization's branding source and, optionally, its settings.

        Most callers use :meth:`set_branding`, :meth:`use_environment_branding`
        or :meth:`reapply_branding` instead; this is the general form.

        Args:
            organization_id:        Scalekit organization ID.
            source:                 ``BRANDING_SOURCE_CUSTOM`` (or ``"CUSTOM"``)
                                    to apply the organization's own branding;
                                    ``BRANDING_SOURCE_ENVIRONMENT`` (or
                                    ``"ENVIRONMENT"``) to fall back to the
                                    environment branding.
            customization_settings: Dict of settings that **replaces** the
                                    organization's saved branding. Keys the
                                    organization does not set inherit the
                                    environment value; an empty string (``""``)
                                    removes the value for this organization.
                                    With ``CUSTOM`` and no settings, the saved
                                    branding is re-applied. Ignored with
                                    ``ENVIRONMENT``.

        Returns:
            Dict with the updated ``branding`` (same shape as :meth:`get_branding`).

        Settings are stored as sent and are not validated field by field, the
        same as the environment branding: send the documented shape.

        Raises:
            ValueError:    If ``source`` is not a known branding source.
            ScalekitError: 400 for ``CUSTOM`` without settings when nothing is
                           saved; 403 if organization branding is not turned on;
                           404 if the organization does not exist.
        """
        body = {"source": _branding_source(source)}
        if customization_settings is not None:
            body["customization_settings"] = customization_settings
        return self._core.request(
            "PUT", "/api/v1/organizations/{}/portal_customizations".format(organization_id),
            body=body,
        )

    def set_branding(self, organization_id, customization_settings):
        """Save and apply an organization's own branding.

        Replaces anything saved before: send every value the organization
        should override. Anything left out falls back to the environment.

        Example::

            client.organization.set_branding("org_123", {
                "portal_customization": {
                    "logo_url": "https://cdn.acme.com/logo.png",
                    "button_color": "#B71C1C",
                },
                "application_customization": {"name": "Acme Portal"},
            })

        Args:
            organization_id:        Scalekit organization ID.
            customization_settings: Dict of settings, same shape as the
                                    environment branding.

        Returns:
            Dict with the updated ``branding``.
        """
        if not isinstance(customization_settings, dict):
            raise ValueError("customization_settings must be a dict")
        return self.update_branding(organization_id, BRANDING_SOURCE_CUSTOM, customization_settings)

    def use_environment_branding(self, organization_id):
        """Switch an organization back to the environment branding.

        The organization's saved branding is kept, so :meth:`reapply_branding`
        can restore it later.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            Dict with the updated ``branding``.
        """
        return self.update_branding(organization_id, BRANDING_SOURCE_ENVIRONMENT)

    def reapply_branding(self, organization_id):
        """Re-apply the branding an organization saved before.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            Dict with the updated ``branding``.

        Raises:
            ScalekitError: 400 if the organization has no saved branding.
        """
        return self.update_branding(organization_id, BRANDING_SOURCE_CUSTOM)

    def get_support_email(self, organization_id):
        """Return the support email an organization's own branding sets.

        The support email appears on the organization's login page and, when
        you send emails through your own email provider, as the
        ``organization_support_email`` template variable.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            The organization's support email, or ``None`` when it uses your
            environment's support email: it uses custom branding that leaves the
            support email empty, or it uses environment branding.

        Raises:
            ScalekitError: 403 if organization branding is not turned on for
                           the environment, 404 if the organization does not exist.
        """
        branding, settings = _saved_settings(self.get_branding(organization_id))
        if branding.get("source") != BRANDING_SOURCE_CUSTOM:
            return None
        section, key = _support_email_location(settings)
        return (settings.get(section) or {}).get(key) or None

    def set_support_email(self, organization_id, support_email):
        """Set the support email for an organization.

        Keeps everything else the organization has saved and changes only the
        support email. The organization switches to custom branding; if it was
        using environment branding, the branding it saved before is re-applied
        along with the new support email.

        Example::

            client.organization.set_support_email("org_123", "support@acme.com")

        Args:
            organization_id: Scalekit organization ID.
            support_email:   The email address to show, such as
                             ``"support@acme.com"``. Surrounding spaces are removed.

        Returns:
            Dict with the updated ``branding``.

        The SDK reads the saved branding and writes it back in a second call,
        so a change saved by someone else in between is overwritten.

        Raises:
            ValueError:    If ``support_email`` is not an email address.
            ScalekitError: 400 if the API rejects the settings; 403 if
                           organization branding is not turned on; 404 if the
                           organization does not exist.
        """
        if not isinstance(support_email, str):
            raise ValueError("support_email must be a string, got {!r}".format(support_email))
        email = support_email.strip()
        local, at, domain = email.partition("@")
        if not local or not at or not domain or " " in email:
            raise ValueError("support_email must be an email address, got {!r}".format(support_email))

        _, settings = _saved_settings(self.get_branding(organization_id))
        section, key = _support_email_location(settings)
        values = settings.get(section)
        if not isinstance(values, dict):
            values = {}
            settings[section] = values
        values[key] = email
        return self.update_branding(organization_id, BRANDING_SOURCE_CUSTOM, settings)

    def remove_support_email(self, organization_id):
        """Remove an organization's own support email, so it uses your environment's.

        Keeps everything else the organization has saved. The organization's
        login page and emails then show your environment's support email, and
        follow any later change to it.

        Nothing is written when the organization sets no support email, or when
        it uses environment branding (it already shows your environment's). In
        the second case a support email in its saved branding stays saved, and
        :meth:`reapply_branding` brings it back with the rest.

        Args:
            organization_id: Scalekit organization ID.

        Returns:
            Dict with the organization's ``branding`` after the change.

        Raises:
            ScalekitError: 403 if organization branding is not turned on; 404 if
                           the organization does not exist.
        """
        response = self.get_branding(organization_id)
        branding, settings = _saved_settings(response)
        if branding.get("source") != BRANDING_SOURCE_CUSTOM:
            return response
        section, key = _support_email_location(settings)
        values = settings.get(section)
        if not isinstance(values, dict) or key not in values:
            return response
        # Remove the key rather than sending "": an empty string is saved as the organization's
        # value and shows no support email, while a missing key uses the environment's.
        del values[key]
        return self.update_branding(organization_id, BRANDING_SOURCE_CUSTOM, settings)

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

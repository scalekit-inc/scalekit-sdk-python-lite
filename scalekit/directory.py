try:
    from typing import Optional
except ImportError:
    pass


class DirectoryClient(object):
    """Manage SCIM directories and browse synced users and groups."""

    def __init__(self, core):
        self._core = core

    def get(self, organization_id, directory_id):
        """Fetch a directory by its ID.

        Args:
            organization_id: Scalekit organization ID that owns the directory.
            directory_id:    Scalekit directory ID (e.g. ``dir_123...``).

        Returns:
            Dict with a ``directory`` key.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/directories/{}".format(organization_id, directory_id)
        )

    def list(self, organization_id, page_size=None, page_token=None):
        """List all directories for an organization.

        Args:
            organization_id: Scalekit organization ID.
            page_size:       Maximum results per page.
            page_token:      Pagination token from a previous response.

        Returns:
            Dict with a ``directories`` list and optional ``next_page_token``.
        """
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request(
            "GET", "/api/v1/organizations/{}/directories".format(organization_id), params=params
        )

    def enable(self, organization_id, directory_id):
        """Enable a previously disabled directory.

        Args:
            organization_id: Scalekit organization ID.
            directory_id:    Scalekit directory ID.

        Returns:
            Dict with the updated ``directory``.
        """
        return self._core.request(
            "PATCH",
            "/api/v1/organizations/{}/directories/{}:enable".format(organization_id, directory_id)
        )

    def disable(self, organization_id, directory_id):
        """Disable an active directory without deleting it.

        Args:
            organization_id: Scalekit organization ID.
            directory_id:    Scalekit directory ID.

        Returns:
            Dict with the updated ``directory``.
        """
        return self._core.request(
            "PATCH",
            "/api/v1/organizations/{}/directories/{}:disable".format(organization_id, directory_id)
        )

    def list_users(self, organization_id, directory_id, page_size=None, page_token=None):
        """List users synced from a SCIM directory.

        Args:
            organization_id: Scalekit organization ID.
            directory_id:    Scalekit directory ID.
            page_size:       Maximum results per page.
            page_token:      Pagination token from a previous response.

        Returns:
            Dict with a ``directory_users`` list.
        """
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request(
            "GET",
            "/api/v1/organizations/{}/directories/{}/users".format(organization_id, directory_id),
            params=params,
        )

    def list_groups(self, organization_id, directory_id, page_size=None, page_token=None):
        """List groups synced from a SCIM directory.

        Args:
            organization_id: Scalekit organization ID.
            directory_id:    Scalekit directory ID.
            page_size:       Maximum results per page.
            page_token:      Pagination token from a previous response.

        Returns:
            Dict with a ``directory_groups`` list.
        """
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request(
            "GET",
            "/api/v1/organizations/{}/directories/{}/groups".format(organization_id, directory_id),
            params=params,
        )

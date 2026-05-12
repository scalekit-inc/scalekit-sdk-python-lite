try:
    from typing import Optional
except ImportError:
    pass


class ConnectionClient(object):
    """Manage SSO connections across your Scalekit environment."""

    def __init__(self, core):
        self._core = core

    def get(self, connection_id):
        """Fetch a connection by its Scalekit ID.

        Args:
            connection_id: Scalekit connection ID (e.g. ``conn_123...``).

        Returns:
            Dict with a ``connection`` key.
        """
        return self._core.request("GET", "/api/v1/connections/{}".format(connection_id))

    def get_by_org(self, organization_id, connection_id):
        """Fetch a connection scoped to a specific organization.

        Args:
            organization_id: Scalekit organization ID.
            connection_id:   Scalekit connection ID.

        Returns:
            Dict with a ``connection`` key.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/connections/{}".format(organization_id, connection_id)
        )

    def list(self, page_size=None, page_token=None):
        """List all connections in the environment.

        Args:
            page_size:  Maximum results per page.
            page_token: Opaque pagination token from a previous response.

        Returns:
            Dict with a ``connections`` list and optional ``next_page_token``.
        """
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request("GET", "/api/v1/connections", params=params)

    def list_by_org(self, organization_id, page_size=None, page_token=None):
        """List all connections belonging to a specific organization.

        Args:
            organization_id: Scalekit organization ID.
            page_size:       Maximum results per page.
            page_token:      Pagination token from a previous response.

        Returns:
            Dict with a ``connections`` list.
        """
        params = {"organization_id": organization_id, "page_size": page_size, "page_token": page_token}
        return self._core.request("GET", "/api/v1/connections", params=params)

    def update(self, connection_id, **kwargs):
        """Update fields on an existing connection.

        Args:
            connection_id: Scalekit connection ID.
            **kwargs:      Fields to update.

        Returns:
            Dict with the updated ``connection``.
        """
        return self._core.request(
            "PATCH", "/api/v1/connections/{}".format(connection_id),
            body={"connection": kwargs}
        )

    def delete(self, connection_id):
        """Permanently delete a connection.

        Args:
            connection_id: Scalekit connection ID.

        Returns:
            Empty dict on success.
        """
        return self._core.request("DELETE", "/api/v1/connections/{}".format(connection_id))

    def enable(self, connection_id):
        """Enable a previously disabled connection.

        Args:
            connection_id: Scalekit connection ID.

        Returns:
            Dict with the updated ``connection``.
        """
        return self._core.request("PATCH", "/api/v1/connections/{}:enable".format(connection_id))

    def disable(self, connection_id):
        """Disable an active connection without deleting it.

        Args:
            connection_id: Scalekit connection ID.

        Returns:
            Dict with the updated ``connection``.
        """
        return self._core.request("PATCH", "/api/v1/connections/{}:disable".format(connection_id))

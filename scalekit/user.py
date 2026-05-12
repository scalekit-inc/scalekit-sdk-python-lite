try:
    from typing import Any, Dict, List, Optional
except ImportError:
    pass


class UserClient(object):
    """Manage users, organization memberships, and role assignments."""

    def __init__(self, core):
        self._core = core

    def get(self, user_id):
        """Fetch a user by their Scalekit ID.

        Args:
            user_id: Scalekit user ID (e.g. ``usr_123...``).

        Returns:
            Dict with a ``user`` key.
        """
        return self._core.request("GET", "/api/v1/users/{}".format(user_id))

    def list(self, page_size=None, page_token=None):
        """List all users in the environment.

        Args:
            page_size:  Maximum number of results per page.
            page_token: Opaque pagination token from a previous response.

        Returns:
            Dict with a ``users`` list and optional ``next_page_token``.
        """
        return self._core.request(
            "GET", "/api/v1/users",
            params={"page_size": page_size, "page_token": page_token},
        )

    def search(self, query, page_size=None, page_token=None):
        """Search all users in the environment by email or name.

        Args:
            query:      Search string (email prefix, name, etc.).
            page_size:  Maximum results per page.
            page_token: Pagination token from a previous response.

        Returns:
            Dict with a ``users`` list.
        """
        return self._core.request(
            "GET", "/api/v1/users:search",
            params={"query": query, "page_size": page_size, "page_token": page_token},
        )

    def update(self, user_id, **kwargs):
        """Update fields on an existing user.

        Pass writable user fields as keyword arguments, e.g.
        ``user_profile={"given_name": "Alice"}``.

        Args:
            user_id:  Scalekit user ID.
            **kwargs: Fields to update.

        Returns:
            Dict with the updated ``user``.
        """
        return self._core.request(
            "PATCH", "/api/v1/users/{}".format(user_id), body=kwargs
        )

    def delete(self, user_id):
        """Permanently delete a user.

        Args:
            user_id: Scalekit user ID.

        Returns:
            Empty dict on success.
        """
        return self._core.request("DELETE", "/api/v1/users/{}".format(user_id))

    def create_and_add_to_org(self, organization_id, user, send_invitation_email=None):
        """Create a new user and add them to an organization in one call.

        Args:
            organization_id:        Scalekit organization ID.
            user:                   Dict of user fields, e.g. ``{"email": "alice@acme.com"}``.
            send_invitation_email:  Set to ``False`` to suppress the welcome email (optional).

        Returns:
            Dict with a ``user`` key containing the created user.
        """
        params = {}
        if send_invitation_email is not None:
            params["send_invitation_email"] = send_invitation_email
        return self._core.request(
            "POST", "/api/v1/organizations/{}/users".format(organization_id),
            body=user,
            params=params if params else None,
        )

    def list_org_users(self, organization_id, page_size=None, page_token=None):
        """List all users who belong to an organization.

        Args:
            organization_id: Scalekit organization ID.
            page_size:       Maximum results per page.
            page_token:      Pagination token from a previous response.

        Returns:
            Dict with a ``users`` list.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/users".format(organization_id),
            params={"page_size": page_size, "page_token": page_token},
        )

    def search_org_users(self, organization_id, query, page_size=None, page_token=None):
        """Search users within a specific organization.

        Args:
            organization_id: Scalekit organization ID.
            query:           Search string.
            page_size:       Maximum results per page.
            page_token:      Pagination token from a previous response.

        Returns:
            Dict with a ``users`` list.
        """
        return self._core.request(
            "GET", "/api/v1/organizations/{}/users:search".format(organization_id),
            params={"query": query, "page_size": page_size, "page_token": page_token},
        )

    def create_membership(self, organization_id, user_id, membership=None):
        """Add an existing user to an organization.

        Args:
            organization_id: Scalekit organization ID.
            user_id:         Scalekit user ID.
            membership:      Dict of membership fields to set (optional).

        Returns:
            Dict with the created ``membership``.
        """
        return self._core.request(
            "POST",
            "/api/v1/memberships/organizations/{}/users/{}".format(organization_id, user_id),
            body=membership or {},
        )

    def delete_membership(self, organization_id, user_id):
        """Remove a user from an organization without deleting the user account.

        Args:
            organization_id: Scalekit organization ID.
            user_id:         Scalekit user ID.

        Returns:
            Empty dict on success.
        """
        return self._core.request(
            "DELETE",
            "/api/v1/memberships/organizations/{}/users/{}".format(organization_id, user_id),
        )

    def update_membership(self, organization_id, user_id, membership):
        """Update a user's membership fields within an organization.

        Args:
            organization_id: Scalekit organization ID.
            user_id:         Scalekit user ID.
            membership:      Dict of membership fields to update.

        Returns:
            Dict with the updated ``membership``.
        """
        return self._core.request(
            "PATCH",
            "/api/v1/memberships/organizations/{}/users/{}".format(organization_id, user_id),
            body=membership,
        )

    def resend_invite(self, organization_id, user_id):
        """Resend the invitation email to a user who has not yet accepted.

        Args:
            organization_id: Scalekit organization ID.
            user_id:         Scalekit user ID.

        Returns:
            Empty dict on success.
        """
        return self._core.request(
            "PATCH",
            "/api/v1/invites/organizations/{}/users/{}/resend".format(organization_id, user_id),
            body={},
        )

    def list_roles(self, organization_id, user_id):
        """List all roles assigned to a user within an organization.

        Args:
            organization_id: Scalekit organization ID.
            user_id:         Scalekit user ID.

        Returns:
            Dict with a ``roles`` list.
        """
        return self._core.request(
            "GET",
            "/api/v1/organizations/{}/users/{}/roles".format(organization_id, user_id),
        )

    def assign_roles(self, organization_id, user_id, roles):
        """Assign one or more roles to a user within an organization.

        Args:
            organization_id: Scalekit organization ID.
            user_id:         Scalekit user ID.
            roles:           List of role objects, e.g. ``[{"role_name": "admin"}]``.

        Returns:
            Dict with the updated ``roles`` list.
        """
        return self._core.request(
            "POST",
            "/api/v1/organizations/{}/users/{}/roles".format(organization_id, user_id),
            body=roles,
        )

    def remove_role(self, organization_id, user_id, role_name):
        """Remove a specific role from a user.

        Args:
            organization_id: Scalekit organization ID.
            user_id:         Scalekit user ID.
            role_name:       Name of the role to remove (e.g. ``"admin"``).

        Returns:
            Empty dict on success.
        """
        return self._core.request(
            "DELETE",
            "/api/v1/organizations/{}/users/{}/roles/{}".format(
                organization_id, user_id, role_name
            ),
        )

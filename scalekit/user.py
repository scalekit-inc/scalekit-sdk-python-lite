try:
    from typing import Any, Dict, List, Optional
except ImportError:
    pass


class UserClient(object):

    def __init__(self, core):
        self._core = core

    def get(self, user_id):
        return self._core.request("GET", "/api/v1/users/{}".format(user_id))

    def list(self, page_size=None, page_token=None):
        return self._core.request(
            "GET", "/api/v1/users",
            params={"page_size": page_size, "page_token": page_token},
        )

    def search(self, query, page_size=None, page_token=None):
        return self._core.request(
            "GET", "/api/v1/users:search",
            params={"query": query, "page_size": page_size, "page_token": page_token},
        )

    def update(self, user_id, **kwargs):
        return self._core.request(
            "PATCH", "/api/v1/users/{}".format(user_id), body=kwargs
        )

    def delete(self, user_id):
        return self._core.request("DELETE", "/api/v1/users/{}".format(user_id))

    def create_and_add_to_org(self, organization_id, user, send_invitation_email=None):
        params = {}
        if send_invitation_email is not None:
            params["send_invitation_email"] = send_invitation_email
        return self._core.request(
            "POST", "/api/v1/organizations/{}/users".format(organization_id),
            body=user,
            params=params if params else None,
        )

    def list_org_users(self, organization_id, page_size=None, page_token=None):
        return self._core.request(
            "GET", "/api/v1/organizations/{}/users".format(organization_id),
            params={"page_size": page_size, "page_token": page_token},
        )

    def search_org_users(self, organization_id, query, page_size=None, page_token=None):
        return self._core.request(
            "GET", "/api/v1/organizations/{}/users:search".format(organization_id),
            params={"query": query, "page_size": page_size, "page_token": page_token},
        )

    def create_membership(self, organization_id, user_id, membership=None):
        return self._core.request(
            "POST",
            "/api/v1/memberships/organizations/{}/users/{}".format(organization_id, user_id),
            body=membership or {},
        )

    def delete_membership(self, organization_id, user_id):
        return self._core.request(
            "DELETE",
            "/api/v1/memberships/organizations/{}/users/{}".format(organization_id, user_id),
        )

    def update_membership(self, organization_id, user_id, membership):
        return self._core.request(
            "PATCH",
            "/api/v1/memberships/organizations/{}/users/{}".format(organization_id, user_id),
            body=membership,
        )

    def resend_invite(self, organization_id, user_id):
        return self._core.request(
            "PATCH",
            "/api/v1/invites/organizations/{}/users/{}/resend".format(organization_id, user_id),
            body={},
        )

    def list_roles(self, organization_id, user_id):
        return self._core.request(
            "GET",
            "/api/v1/organizations/{}/users/{}/roles".format(organization_id, user_id),
        )

    def assign_roles(self, organization_id, user_id, roles):
        return self._core.request(
            "POST",
            "/api/v1/organizations/{}/users/{}/roles".format(organization_id, user_id),
            body=roles,
        )

    def remove_role(self, organization_id, user_id, role_name):
        return self._core.request(
            "DELETE",
            "/api/v1/organizations/{}/users/{}/roles/{}".format(
                organization_id, user_id, role_name
            ),
        )

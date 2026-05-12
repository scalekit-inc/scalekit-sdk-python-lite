try:
    from typing import Optional
except ImportError:
    pass

from scalekit._core import CoreClient


class DirectoryClient(object):

    def __init__(self, core):
        self._core = core

    def get(self, organization_id, directory_id):
        return self._core.request(
            "GET", "/api/v1/organizations/{}/directories/{}".format(organization_id, directory_id)
        )

    def list(self, organization_id, page_size=None, page_token=None):
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request(
            "GET", "/api/v1/organizations/{}/directories".format(organization_id), params=params
        )

    def enable(self, organization_id, directory_id):
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/directories/{}:enable".format(organization_id, directory_id)
        )

    def disable(self, organization_id, directory_id):
        return self._core.request(
            "PATCH", "/api/v1/organizations/{}/directories/{}:disable".format(organization_id, directory_id)
        )

    def list_users(self, organization_id, directory_id, page_size=None, page_token=None):
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request(
            "GET",
            "/api/v1/organizations/{}/directories/{}/users".format(organization_id, directory_id),
            params=params,
        )

    def list_groups(self, organization_id, directory_id, page_size=None, page_token=None):
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request(
            "GET",
            "/api/v1/organizations/{}/directories/{}/groups".format(organization_id, directory_id),
            params=params,
        )

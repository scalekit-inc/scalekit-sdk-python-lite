try:
    from typing import Optional
except ImportError:
    pass

from scalekit._core import CoreClient


class ConnectionClient(object):

    def __init__(self, core):
        self._core = core

    def get(self, connection_id):
        return self._core.request("GET", "/api/v1/connections/{}".format(connection_id))

    def get_by_org(self, organization_id, connection_id):
        return self._core.request(
            "GET", "/api/v1/organizations/{}/connections/{}".format(organization_id, connection_id)
        )

    def list(self, page_size=None, page_token=None):
        params = {"page_size": page_size, "page_token": page_token}
        return self._core.request("GET", "/api/v1/connections", params=params)

    def list_by_org(self, organization_id, page_size=None, page_token=None):
        params = {"organization_id": organization_id, "page_size": page_size, "page_token": page_token}
        return self._core.request("GET", "/api/v1/connections", params=params)

    def update(self, connection_id, **kwargs):
        return self._core.request(
            "PATCH", "/api/v1/connections/{}".format(connection_id),
            body={"connection": kwargs}
        )

    def delete(self, connection_id):
        return self._core.request("DELETE", "/api/v1/connections/{}".format(connection_id))

    def enable(self, connection_id):
        return self._core.request("PATCH", "/api/v1/connections/{}:enable".format(connection_id))

    def disable(self, connection_id):
        return self._core.request("PATCH", "/api/v1/connections/{}:disable".format(connection_id))

#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sslkeys import SSLKeysRepository
from maasservicelayer.models.sslkeys import SSLKey, SSLKeyBuilder
from maasservicelayer.services.base import BaseService


class SSLKeysService(BaseService[SSLKey, SSLKeysRepository, SSLKeyBuilder]):
    def __init__(
        self,
        context: Context,
        sslkey_repository: SSLKeysRepository,
    ):
        super().__init__(context, sslkey_repository)

    async def update_by_id(self, id, resource, etag_if_match=None):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_many(self, query, resource):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_one(self, query, resource, etag_if_match=None):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def _update_resource(
        self, existing_resource, resource, etag_if_match=None
    ):
        raise NotImplementedError("Update is not supported for SSL keys")

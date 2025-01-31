#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.sslkeys import SSLKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.sslkeys import (
    SSLKeyClauseFactory,
    SSLKeysRepository,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.services.base import BaseService


class SSLKeysService(BaseService[SSLKey, SSLKeysRepository, SSLKeyBuilder]):
    def __init__(
        self,
        context: Context,
        sslkey_repository: SSLKeysRepository,
    ):
        super().__init__(context, sslkey_repository)

    async def pre_create_hook(self, builder: SSLKeyBuilder) -> None:
        # TODO: create a method on the builder to access value only if they are != Unset
        assert isinstance(builder.key, str)
        sslkey_exists = await self.exists(
            query=QuerySpec(where=SSLKeyClauseFactory.with_key(builder.key))
        )
        if sslkey_exists:
            raise AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="The SSL key already exist.",
                    )
                ]
            )

    async def update_by_id(self, id, builder, etag_if_match=None):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_many(self, query, builder):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def update_one(self, query, builder, etag_if_match=None):
        raise NotImplementedError("Update is not supported for SSL keys")

    async def _update_resource(
        self, existing_resource, builder, etag_if_match=None
    ):
        raise NotImplementedError("Update is not supported for SSL keys")

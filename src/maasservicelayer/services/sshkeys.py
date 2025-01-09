# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sshkeys import SshKeysRepository
from maasservicelayer.models.sshkeys import SshKey
from maasservicelayer.services._base import BaseService


class SshKeysService(BaseService[SshKey, SshKeysRepository]):
    def __init__(
        self, context: Context, sshkeys_repository: SshKeysRepository
    ):
        super().__init__(context, sshkeys_repository)

    async def update_by_id(self, id, resource, etag_if_match=None):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def update_many(self, query, resource):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def update_one(self, query, resource, etag_if_match=None):
        raise NotImplementedError("Update is not supported for ssh keys")

    async def _update_resource(
        self, existing_resource, resource, etag_if_match=None
    ):
        raise NotImplementedError("Update is not supported for ssh keys")

# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.ssh_host_keys import TrustedSshHostKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ssh_host_keys import (
    TrustedSshHostKeyRepository,
)
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey
from maasservicelayer.services.base import BaseService


class TrustedSshHostKeysService(
    BaseService[
        TrustedSshHostKey,
        TrustedSshHostKeyRepository,
        TrustedSshHostKeyBuilder,
    ]
):
    def __init__(
        self,
        context: Context,
        repository: TrustedSshHostKeyRepository,
    ):
        super().__init__(context, repository)

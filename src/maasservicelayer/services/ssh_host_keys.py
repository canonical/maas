# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.fips import is_fips_enabled, validate_fips_ssh_public_key
from maasservicelayer.builders.ssh_host_keys import TrustedSshHostKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ssh_host_keys import (
    TrustedSshHostKeyRepository,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    FIPSViolationException,
)
from maasservicelayer.exceptions.constants import FIPS_VIOLATION_TYPE
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

    async def pre_create_hook(self, builder: TrustedSshHostKeyBuilder) -> None:
        if is_fips_enabled():
            normalized_key = f"{builder.key_type} {builder.public_key}"
            violation = validate_fips_ssh_public_key(normalized_key)
            if violation is not None:
                raise FIPSViolationException(
                    details=[
                        BaseExceptionDetail(
                            type=FIPS_VIOLATION_TYPE,
                            message=violation,
                        )
                    ]
                )

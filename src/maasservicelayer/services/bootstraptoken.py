# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.bootstraptokens import BootstrapTokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensRepository,
)
from maasservicelayer.models.bootstraptokens import BootstrapToken
from maasservicelayer.services.base import BaseService


class BootstrapTokensService(
    BaseService[
        BootstrapToken, BootstrapTokensRepository, BootstrapTokenBuilder
    ]
):
    def __init__(
        self, context: Context, repository: BootstrapTokensRepository
    ) -> None:
        super().__init__(context, repository)

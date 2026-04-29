# Copyright 2025-2026 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import structlog

from maascommon.logging.security import (
    AUTHN_TOKEN_CREATED,
    AUTHN_TOKEN_DELETED,
    hash_token_for_logging,
    SECURITY,
)
from maasservicelayer.builders.bootstraptokens import BootstrapTokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensRepository,
)
from maasservicelayer.models.bootstraptokens import BootstrapToken
from maasservicelayer.services.base import BaseService

logger = structlog.get_logger()


class BootstrapTokensService(
    BaseService[
        BootstrapToken, BootstrapTokensRepository, BootstrapTokenBuilder
    ]
):
    def __init__(
        self, context: Context, repository: BootstrapTokensRepository
    ) -> None:
        super().__init__(context, repository)

    async def post_create_hook(self, resource):
        logger.info(
            f"{AUTHN_TOKEN_CREATED}:bootstraptoken",
            type=SECURITY,
            token_hash=hash_token_for_logging(resource.secret),
        )

    async def post_create_many_hook(self, resources):
        for resource in resources:
            logger.info(
                f"{AUTHN_TOKEN_CREATED}:bootstraptoken",
                type=SECURITY,
                token_hash=hash_token_for_logging(resource.secret),
            )

    async def post_delete_hook(self, resource) -> None:
        logger.info(
            f"{AUTHN_TOKEN_DELETED}:bootstraptoken",
            type=SECURITY,
            token_hash=hash_token_for_logging(resource.secret),
        )

    async def post_delete_many_hook(self, resources) -> None:
        for resource in resources:
            logger.info(
                f"{AUTHN_TOKEN_DELETED}:bootstraptoken",
                type=SECURITY,
                token_hash=hash_token_for_logging(resource.secret),
            )

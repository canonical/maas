# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.agentcertificates import AgentCertificateBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.agentcertificates import (
    AgentCertificatesRepository,
)
from maasservicelayer.models.agentcertificates import AgentCertificate
from maasservicelayer.services.base import BaseService


class AgentCertificateService(
    BaseService[
        AgentCertificate, AgentCertificatesRepository, AgentCertificateBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        repository: AgentCertificatesRepository,
    ):
        super().__init__(context, repository)

    async def update_by_id(self, id, builder, etag_if_match=None):
        raise NotImplementedError(
            "Update is not supported for agent certificates"
        )

    async def update_many(self, query, builder):
        raise NotImplementedError(
            "Update is not supported for agent certificates"
        )

    async def update_one(self, query, builder, etag_if_match=None):
        raise NotImplementedError(
            "Update is not supported for agent certificates"
        )

    async def _update_resource(
        self, existing_resource, builder, etag_if_match=None
    ):
        raise NotImplementedError(
            "Update is not supported for agent certificates"
        )

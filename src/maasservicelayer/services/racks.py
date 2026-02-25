# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import secrets
from typing import List
from urllib.parse import urlparse

import aiofiles

from maasservicelayer.builders.bootstraptokens import BootstrapTokenBuilder
from maasservicelayer.builders.racks import RackBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.agents import AgentsClauseFactory
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensClauseFactory,
)
from maasservicelayer.db.repositories.racks import RacksRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.configurations import MAASUrlConfig
from maasservicelayer.models.racks import Rack, RackWithSummary
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.bootstraptoken import BootstrapTokensService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.secrets import SecretsService
from maasservicelayer.utils.date import utcnow
from provisioningserver.certificates import (
    Certificate,
    get_maas_cluster_cert_paths,
)

SECRET_TTL = timedelta(minutes=5)
INTERNAL_API_PORT = 5242


class RacksService(BaseService[Rack, RacksRepository, RackBuilder]):
    resource_logging_name = "rack"

    def __init__(
        self,
        context: Context,
        repository: RacksRepository,
        agents_service: AgentsService,
        bootstraptokens_service: BootstrapTokensService,
        configurations_service: ConfigurationsService,
        secrets_service: SecretsService,
    ) -> None:
        super().__init__(context, repository)
        self.agents_service = agents_service
        self.bootstraptokens_service = bootstraptokens_service
        self.configurations_service = configurations_service
        self.secrets_service = secrets_service

    async def post_delete_hook(self, resource: Rack) -> None:
        # cascade delete for a single resource
        await self.bootstraptokens_service.delete_many(
            query=QuerySpec(
                where=BootstrapTokensClauseFactory.with_rack_id(resource.id)
            )
        )
        await self.agents_service.delete_many(
            query=QuerySpec(
                where=AgentsClauseFactory.with_rack_id(resource.id)
            )
        )

    async def post_delete_many_hook(self, resources: List[Rack]) -> None:
        # cascade delete for multiple resources
        rack_ids = [resource.id for resource in resources]

        await self.bootstraptokens_service.delete_many(
            query=QuerySpec(
                where=BootstrapTokensClauseFactory.with_rack_id_in(rack_ids)
            )
        )
        await self.agents_service.delete_many(
            query=QuerySpec(
                where=AgentsClauseFactory.with_rack_id_in(rack_ids)
            )
        )

    async def generate_bootstrap_token(self, resource: Rack) -> dict:
        """
        Generate the bootstrap token used for MAAS Agent enrollment.

        The bootstrap token contains the necessary information to establish
        secure communication between a running MAAS region and a rack. In
        practice, this communication occurs between MAAS and the MAAS Agent
        running on the rack.

        The generated token includes the following components:
        - secret: a short-lived authentication secret used by the Agent to prove
          its identity to MAAS. It is generated at the time the token is created
          and is stored in MAAS for future verification of the Agent.
        - fingerprint: a fingerprint of the MAAS TLS certificate, used by the
          Agent to authenticate the MAAS server during HTTPS communication.
        - url: the URL the Agent must use to send its registration request to
          MAAS.
        """
        rack_id = resource.id

        # secret: 32 random bytes as hex string (64 chars)
        secret = secrets.token_hex(32)

        # fingerprint: cluster certificate (internal API)
        fingerprint = ""
        cluster_cert_paths = get_maas_cluster_cert_paths()
        if cluster_cert_paths is not None:
            cert_path, key_path, cacerts_path = cluster_cert_paths
            try:
                async with (
                    aiofiles.open(key_path, "r") as key_file,
                    aiofiles.open(cert_path, "r") as cert_file,
                ):
                    key = await key_file.read()
                    cert = await cert_file.read()

                cacerts = ""
                try:
                    async with aiofiles.open(
                        cacerts_path, "r"
                    ) as cacerts_file:
                        cacerts = await cacerts_file.read()
                except (FileNotFoundError, IOError):
                    pass

                certificate = Certificate.from_pem(
                    key,
                    cert,
                    ca_certs_material=cacerts,
                )
                fingerprint = certificate.cert_hash()
            except (FileNotFoundError, IOError):
                pass

        # url: internal API
        maas_url = await self.configurations_service.get(
            name=MAASUrlConfig.name
        )
        parsed_url = urlparse(maas_url)
        internal_api_url = f"https://{parsed_url.hostname}:{INTERNAL_API_PORT}"

        # bootstrap token: secret, (fingerprint, url)
        token = {
            "secret": secret,
            "fingerprint": fingerprint,
            "url": internal_api_url,
        }

        # once the token is created, we store the short-lived secret
        bootstraptoken_builder = BootstrapTokenBuilder(
            rack_id=rack_id,
            secret=secret,
            expires_at=utcnow() + SECRET_TTL,
        )
        await self.bootstraptokens_service.create(bootstraptoken_builder)

        return token

    async def list_with_summary(
        self, page: int, size: int
    ) -> ListResult[RackWithSummary]:
        return await self.repository.list_with_summary(page, size)

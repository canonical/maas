#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasservicelayer.services import ServiceCollectionV3


class AgentHandler(Handler):
    """
    MAAS Agent API handler provides collection of handlers that can be called
    by the Agent to fetch configuration for its various services or push back
    data that should be known to MAAS Region Controller
    """

    @handler(
        path="/agents/{system_id}/services/{service_name}/config",
        methods=["GET"],
    )
    async def get_agent_service_config(
        self,
        system_id: str,
        service_name: str,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:

        tokens = await services.agents.get_service_configuration(
            system_id, service_name
        )

        return tokens

# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.internal.models.responses.agent import (
    AgentConfigResponse,
    AgentSignedCertificateResponse,
)
from maasapiserver.v3.constants import V3_INTERNAL_API_PREFIX


class TestAgentConfigResponse:
    def test_from_model(self) -> None:
        maas_url = "https://example.com:5240/MAAS"
        rpc_secret = "mock-rpc-secret"
        system_id = "abc123"
        temporal = {"encryption_key": "mock-encryption-key"}
        base_hyperlink = f"{V3_INTERNAL_API_PREFIX}/agents/mock-uuid/config"

        agent_config_response = AgentConfigResponse.from_model(
            maas_url=maas_url,
            rpc_secret=rpc_secret,
            system_id=system_id,
            temporal=temporal,
            self_base_hyperlink=base_hyperlink,
        )

        assert maas_url == agent_config_response.maas_url
        assert rpc_secret == agent_config_response.rpc_secret
        assert system_id == agent_config_response.system_id
        assert temporal == agent_config_response.temporal
        assert "AgentSignedCertificate" == agent_config_response.kind
        assert base_hyperlink == agent_config_response.hal_links.self.href


class TestAgentSignedCertificateResponse:
    def test_from_model(self) -> None:
        certificate = "certificate"
        ca = "ca"

        agent_cs_response = AgentSignedCertificateResponse.from_model(
            certificate=certificate,
            ca=ca,
            self_base_hyperlink=f"{V3_INTERNAL_API_PREFIX}/agents:enroll",
        )

        assert certificate == agent_cs_response.certificate
        assert (
            f"{V3_INTERNAL_API_PREFIX}/agents:enroll"
            == agent_cs_response.hal_links.self.href
        )

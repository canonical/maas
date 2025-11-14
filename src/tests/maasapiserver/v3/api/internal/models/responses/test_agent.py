# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.internal.models.responses.agent import (
    AgentSignedCertificateResponse,
)
from maasapiserver.v3.constants import V3_INTERNAL_API_PREFIX


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

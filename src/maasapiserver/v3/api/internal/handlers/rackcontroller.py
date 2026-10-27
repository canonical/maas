# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from typing import Annotated

from fastapi import Depends, Response
from OpenSSL import crypto
import structlog

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    ServiceUnavailableErrorBodyResponse,
    UnauthorizedBodyResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.internal.models.requests.rackcontroller import (
    RackControllerEnrollRequest,
)
from maasapiserver.v3.api.internal.models.responses.rackcontroller import (
    RackControllerConfigResponse,
    RackControllerDHCPDataResponse,
    RackControllerSignedCertificateResponse,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.constants import V3_INTERNAL_API_PREFIX
from maascommon.logging.security import (
    AUTHN_TOKEN_REUSED,
    BOOTSTRAP_TOKEN,
    hash_token_for_logging,
    SECURITY,
)
from maasservicelayer.builders.rackcontrollers import RackControllerBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensClauseFactory,
)
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.db.repositories.rackcontrollers import (
    RackControllersClauseFactory,
)
from maasservicelayer.db.repositories.racks import RacksClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
    PRECONDITION_FAILED,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.secrets import (
    MAASCACertificateSecret,
    RPCSharedSecret,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.date import utcnow
from provisioningserver.certificates import Certificate, CertificateRequest
from provisioningserver.config import ClusterConfiguration

logger = structlog.get_logger()


async def fetch_maas_ca_cert(services: ServiceCollectionV3) -> Certificate:
    secret_maas_ca = await services.secrets.get_composite_secret(
        MAASCACertificateSecret(), default=None
    )
    ca_cert = Certificate.from_pem(
        secret_maas_ca["key"],
        secret_maas_ca["cert"],
        ca_certs_material=secret_maas_ca.get("cacert", ""),
    )
    return ca_cert


def sign_certificate_request(
    ca_cert: Certificate, csr_pem: str
) -> Certificate:
    """
    Signs a PEM-encoded Certificate Signing Request (CSR) using a CA

    Inputs
    - ca_cert: the Certificate Authority (CA) used to sign the CSR.
    - csr_pem (str): PEM-encoded certificate signing request to be signed.

    Outputs
    - signed certificate
    """
    csr = crypto.load_certificate_request(
        crypto.FILETYPE_PEM, csr_pem.encode()
    )
    request = CertificateRequest(key=csr.get_pubkey(), csr=csr)

    signed_cert = ca_cert.sign_certificate_request(request)
    return signed_cert


class RackControllerHandler(Handler):
    """
    Rack controller API handler provides a collection of handlers that can be called
    by the rack controller to fetch configuration for its various services or push back
    data that should be known to MAAS Region Controller
    """

    @handler(
        path="/rack_controllers/{system_id}/services/{service_name}/config",
        methods=["GET"],
    )
    async def get_rack_controller_service_config(
        self,
        system_id: str,
        service_name: str,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        tokens = await services.rack_controllers.get_service_configuration(
            system_id, service_name
        )

        return tokens

    @handler(
        path="/rack_controllers/{uuid}/config",
        methods=["GET"],
        responses={
            200: {
                "model": RackControllerConfigResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
            503: {"model": ServiceUnavailableErrorBodyResponse},
        },
        status_code=200,
    )
    async def get_rack_controller_config(
        self,
        uuid: str,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RackControllerConfigResponse:
        rack_controller = await services.rack_controllers.get_one(
            QuerySpec(where=RackControllersClauseFactory.with_uuid(uuid))
        )
        if not rack_controller:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Could not find rack controller with UUID {uuid}.",
                    )
                ]
            )

        maas_url = await services.configurations.get("maas_url")

        rpc_shared_secret_data = await services.secrets.get_composite_secret(
            RPCSharedSecret(), default=None
        )
        if rpc_shared_secret_data and "secret" in rpc_shared_secret_data:
            rpc_secret = rpc_shared_secret_data["secret"]
        else:
            raise ServiceUnavailableException(
                details=[
                    BaseExceptionDetail(
                        type=PRECONDITION_FAILED,
                        message="RPC secret is not configured. Please ensure MAAS is properly initialized.",
                    )
                ]
            )

        system_id = ""
        if rack_controller.node_id:
            node = await services.nodes.get_one(
                QuerySpec(
                    where=NodeClauseFactory.with_id(rack_controller.node_id)
                )
            )
            if node:
                system_id = node.system_id

        temporal_host = ""
        with ClusterConfiguration.open() as cfg:
            temporal_host = cfg.temporal_server

        response.headers["ETag"] = rack_controller.etag()
        return RackControllerConfigResponse.from_model(
            maas_url=maas_url,
            rpc_secret=rpc_secret,
            system_id=system_id,
            temporal={"encryption_key": rpc_secret, "host": temporal_host},
            self_base_hyperlink=f"{V3_INTERNAL_API_PREFIX}/rack_controllers/{uuid}/config",
        )

    @handler(
        path="/rack_controllers/{system_id}/dhcp_data",
        methods=["GET"],
        responses={
            200: {"model": RackControllerDHCPDataResponse},
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
    )
    async def get_rack_controller_dhcp_data(
        self,
        system_id: str,
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> RackControllerDHCPDataResponse:
        dhcp_data = await services.dhcp.get_kea_dhcp_data_for_rack_controller(
            system_id
        )
        return RackControllerDHCPDataResponse.from_model(
            dhcp_data=dhcp_data,
            self_base_hyperlink=f"{V3_INTERNAL_API_PREFIX}/rack_controllers/{system_id}/dhcp_data",
        )

    @handler(
        path="/rack_controllers:enroll",
        methods=["POST"],
        responses={
            201: {
                "model": RackControllerSignedCertificateResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            401: {"model": UnauthorizedBodyResponse},
        },
        status_code=201,
    )
    async def enroll_rack_controller(
        self,
        rack_controller_enroll_request: RackControllerEnrollRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> RackControllerSignedCertificateResponse:
        query_bootstraptoken = QuerySpec(
            where=BootstrapTokensClauseFactory.with_secret(
                rack_controller_enroll_request.secret
            )
        )
        bootstraptoken = await services.bootstraptokens.get_one(
            query=query_bootstraptoken
        )
        if bootstraptoken is None or utcnow() >= bootstraptoken.expires_at:
            if bootstraptoken:
                logger.info(
                    f"{AUTHN_TOKEN_REUSED}:{BOOTSTRAP_TOKEN}",
                    type=SECURITY,
                    token_hash=hash_token_for_logging(
                        rack_controller_enroll_request.secret
                    ),
                )
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Bootstrap token invalid or expired.",
                    )
                ]
            )
        rack = await services.racks.get_one(
            QuerySpec(
                where=RacksClauseFactory.with_rack_id(bootstraptoken.rack_id)
            )
        )
        if rack is None:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="The bootstrap token is invalid or no longer associated with a valid resource.",
                    )
                ]
            )

        # load and sign
        ca_cert = await fetch_maas_ca_cert(services)
        signed_cert = await asyncio.to_thread(
            sign_certificate_request,
            ca_cert,
            rack_controller_enroll_request.csr,
        )

        rack_controller_common_name = signed_cert.cert.get_subject().CN
        if rack_controller_common_name is None:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Certificate must have a Common Name (CN).",
                    )
                ]
            )
        cert_pem_bytes = crypto.dump_certificate(
            crypto.FILETYPE_PEM, signed_cert.cert
        )

        # create RackController (bootstrap token is deleted once the rack controller is enrolled)
        a_builder = RackControllerBuilder(
            uuid=rack_controller_common_name, rack_id=rack.id
        )
        rack_controller = await services.rack_controllers.create(a_builder)
        await services.bootstraptokens.delete_one(query_bootstraptoken)

        response.headers["ETag"] = rack_controller.etag()
        return RackControllerSignedCertificateResponse.from_model(
            certificate=cert_pem_bytes.decode("utf-8"),
            ca=crypto.dump_certificate(
                crypto.FILETYPE_PEM, ca_cert.cert
            ).decode("utf-8"),
            self_base_hyperlink=f"{V3_INTERNAL_API_PREFIX}/rack_controllers:enroll",
        )

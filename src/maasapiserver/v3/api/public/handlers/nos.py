# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Iterator, Optional

from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
import structlog

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maascommon.fields import normalise_macaddress
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.image_local_files import CHUNK_SIZE

logger = structlog.get_logger()


class OnieHeaders(BaseModel):
    """Headers that come out of a ONIE request for installer."""

    eth_address: str = Field(alias="onie-eth-addr")

    # Additional ONIE headers for future use (e.g., architecture matching)
    serial_number: Optional[str] = Field(
        default=None, alias="onie-serial-number"
    )
    vendor_id: Optional[str] = Field(default=None, alias="onie-vendor-id")
    machine: Optional[str] = Field(default=None, alias="onie-machine")
    machine_rev: Optional[str] = Field(default=None, alias="onie-machine-rev")
    arch: Optional[str] = Field(default=None, alias="onie-arch")
    security_key: Optional[str] = Field(
        default=None, alias="onie-security-key"
    )
    operation: Optional[str] = Field(default=None, alias="onie-operation")
    version: Optional[str] = Field(default=None, alias="onie-version")

    @staticmethod
    def from_request(request: Request) -> Optional["OnieHeaders"]:
        onie_headers = {k.lower(): v for k, v in request.headers.items()}

        try:
            return OnieHeaders(**onie_headers)
        except ValidationError:
            return None


class NOSInstallerHandler(Handler):
    """NOS Installer API handler."""

    TAGS = ["Onie"]

    @handler(
        path="/nos-installer",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "content": {
                    "application/octet-stream": {
                        "schema": {
                            "type": "string",
                            "format": "binary",
                        }
                    }
                },
                "description": "NOS installer binary",
            },
            404: {"model": NotFoundBodyResponse},
            400: {"model": BadRequestBodyResponse},
        },
        response_model_exclude_none=True,
        dependencies=[],
    )
    async def get_nos_installer(
        self,
        request: Request,
        services_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Serve NOS installer binary.

        This endpoint:
        - Receives ONIE headers from the switch
        - Checks if an installer is assigned to the switch
        - If assigned, streams the installer binary to the switch

        """
        onie_headers = OnieHeaders.from_request(request)

        mac_address = onie_headers.eth_address if onie_headers else None
        if not mac_address:
            logger.debug(
                "nos_installer_request_missing_mac",
                headers=dict(request.headers),
            )
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="MAC address not found in headers",
                    )
                ]
            )

        mac_address = normalise_macaddress(mac_address)

        installer_file = await services_collection.switches.get_installer_file_for_switch(
            mac_address=mac_address
        )

        if not installer_file:
            logger.debug(
                "nos_installer_not_assigned",
                mac_address=mac_address,
            )
            raise NotFoundException()

        file_path, filename, file_size = installer_file

        logger.info(
            "nos_installer_serving",
            mac_address=mac_address,
            filename=filename,
            size=file_size,
        )

        def file_stream() -> Iterator[bytes]:
            with open(file_path, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    yield chunk

        return StreamingResponse(
            content=file_stream(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(file_size),
            },
        )

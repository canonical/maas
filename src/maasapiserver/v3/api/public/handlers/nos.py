# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Annotated, AsyncIterator

from aiofiles import open as aiofiles_open
from fastapi import Depends, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import structlog

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.image_local_files import CHUNK_SIZE

logger = structlog.get_logger()


class OnieHeaders(BaseModel):
    """ONIE headers from switch installer request."""

    onie_eth_addr: MacAddress
    onie_serial_number: str | None = None
    onie_vendor_id: str | None = None
    onie_machine: str | None = None
    onie_machine_rev: str | None = None
    onie_arch: str | None = None
    onie_security_key: str | None = None
    onie_operation: str | None = None
    onie_version: str | None = None


async def get_onie_headers(
    onie_eth_addr: Annotated[MacAddress, Header()],
    onie_serial_number: Annotated[str | None, Header()] = None,
    onie_vendor_id: Annotated[str | None, Header()] = None,
    onie_machine: Annotated[str | None, Header()] = None,
    onie_machine_rev: Annotated[str | None, Header()] = None,
    onie_arch: Annotated[str | None, Header()] = None,
    onie_security_key: Annotated[str | None, Header()] = None,
    onie_operation: Annotated[str | None, Header()] = None,
    onie_version: Annotated[str | None, Header()] = None,
) -> OnieHeaders:
    return OnieHeaders(
        onie_eth_addr=onie_eth_addr,
        onie_serial_number=onie_serial_number,
        onie_vendor_id=onie_vendor_id,
        onie_machine=onie_machine,
        onie_machine_rev=onie_machine_rev,
        onie_arch=onie_arch,
        onie_security_key=onie_security_key,
        onie_operation=onie_operation,
        onie_version=onie_version,
    )


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
        headers: OnieHeaders = Depends(get_onie_headers),  # noqa: B008
        services_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Serve NOS installer binary.

        This endpoint:
        - Receives ONIE headers from the switch
        - Checks if an installer is assigned to the switch
        - If assigned, streams the installer binary to the switch

        """
        installer_file = (
            await services_collection.switches.get_installer_file_for_switch(
                mac_address=headers.onie_eth_addr
            )
        )

        if not installer_file:
            logger.debug(
                "nos_installer_not_assigned",
                mac_address=headers.onie_eth_addr,
            )
            raise NotFoundException()

        file_path, filename, file_size = installer_file

        logger.info(
            "nos_installer_serving",
            mac_address=headers.onie_eth_addr,
            filename=filename,
            size=file_size,
        )

        async def file_stream() -> AsyncIterator[bytes]:
            async with aiofiles_open(file_path, "rb") as f:
                while chunk := await f.read(CHUNK_SIZE):
                    yield chunk

        return StreamingResponse(
            content=file_stream(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(file_size),
            },
        )

# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Iterator, Optional

from fastapi import Depends, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maascommon.fields import normalise_macaddress
from maascommon.utils.images import get_bootresource_store_path
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3

_FIVE_MB = 5 * (2**10) * (2**10)


class OnieHeaders(BaseModel):
    """Headers that come out of a ONIE request for installer."""

    eth_address: str = Field(alias="onie-eth-addr")

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
            404: {"description": "No installer assigned or switch not found"},
            400: {"description": "Bad request - MAC address not found"},
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
        - #TODO Verifies the installer arch matches the switch arch
        - If assigned, streams the installer binary to the switch

        """
        # Get MAC address from query parameter
        onie_headers = OnieHeaders.from_request(request)

        mac_address = onie_headers.eth_address if onie_headers else None
        if not mac_address:
            return PlainTextResponse(
                content="MAC address not found in headers",
                status_code=400,
            )

        # Normalize MAC address to ensure consistent lookups
        mac_address = normalise_macaddress(mac_address)

        try:
            # Check if switch has an assigned installer
            boot_resource_id = (
                await services_collection.switches.check_installer_for_switch(
                    mac_address=mac_address
                )
            )
        except NotFoundException:
            # Switch not found - return 404 to avoid leaking information
            # about which switches are registered
            return PlainTextResponse(
                content="",
                status_code=404,  # Not Found
            )

        if not boot_resource_id:
            # No installer assigned yet or switch not in correct state
            return PlainTextResponse(
                content="",
                status_code=404,  # Not Found
            )

        # Get the boot resource
        try:
            boot_resource = await services_collection.boot_resources.get_by_id(
                id=boot_resource_id
            )
            if not boot_resource:
                # Boot resource not found - return 404
                return PlainTextResponse(
                    content="",
                    status_code=404,
                )

            # Get the latest complete resource set for this boot resource
            resource_set = await services_collection.boot_resource_sets.get_latest_complete_set_for_boot_resource(
                boot_resource.id
            )
            if not resource_set:
                # No complete resource set - return 404
                return PlainTextResponse(
                    content="",
                    status_code=404,
                )

            # Get the files in the resource set
            files = await services_collection.boot_resource_files.get_files_in_resource_set(
                resource_set.id
            )
            if not files:
                # No files in resource set - return 404
                return PlainTextResponse(
                    content="",
                    status_code=404,
                )
        except NotFoundException:
            # Any boot resource related lookup failed - return 404
            return PlainTextResponse(
                content="",
                status_code=404,
            )

        # Use the first file (uploaded boot resources typically have one file)
        boot_file = files[0]

        # Get the actual file path on disk
        file_path = get_bootresource_store_path() / boot_file.filename_on_disk

        # Stream the file content using standard library
        def file_stream() -> Iterator[bytes]:
            with open(file_path, "rb") as f:
                while chunk := f.read(_FIVE_MB):
                    yield chunk

        return StreamingResponse(
            content=file_stream(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{boot_file.filename}"',
                "Content-Length": str(boot_file.size),
            },
        )

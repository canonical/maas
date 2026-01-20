# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum
import os
from pathlib import Path
from typing import assert_never, AsyncIterator, Protocol

import aiofiles
from fastapi import Depends, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
import structlog
import tempita

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.utils.images import get_bootresource_store_path
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3

_FIVE_MB = 5 * (2**10) * (2**10)
_SNAP_COMMON = Path(os.environ.get("SNAP_COMMON", ""))
logger = structlog.getLogger()


class OnieHeaders(BaseModel):
    """Headers that come out of a ONIE request for installer."""

    serial_number: str = Field(alias="onie-serial-number")
    eth_address: str = Field(alias="onie-eth-addr")
    vendor_id: str = Field(alias="onie-vendor-id")
    machine: str = Field(alias="onie-machine")
    machine_rev: str = Field(alias="onie-machine-rev")
    arch: str = Field(alias="onie-arch")
    security_key: str = Field(alias="onie-security-key")
    operation: str = Field(alias="onie-operation")
    version: str = Field(alias="onie-version")

    @staticmethod
    def from_request(request: Request) -> "OnieHeaders | None":
        headers = request.headers
        onie_headers = {
            k: v for k, v in headers.items() if k.startswith("onie")
        }

        try:
            return OnieHeaders(**onie_headers)
        except ValidationError:
            return None


class TetherScriptRequest(BaseModel):
    """Request body for the tether script endpoint."""

    pass  # No body needed, all info comes from headers


class InstallerRequest(BaseModel):
    """Request body sent by the tether script."""

    mac_address: str = Field(
        ..., description="MAC address of the switch's management port"
    )


def _find_nos_script(filename: str) -> Path:
    """Find a NOS script file in the builtin_scripts directory.

    Uses the metadataserver module location to find scripts, which works
    in both development and snap environments.

    Args:
        filename: Name of the script file to find

    Returns:
        Path to the script file

    Raises:
        FileNotFoundError: If the script file cannot be found
    """
    # Import metadataserver to find its installation location
    import metadataserver

    metadataserver_path = Path(metadataserver.__file__).parent
    script_path = (
        metadataserver_path / "builtin_scripts" / "nos_scripts" / filename
    )

    if script_path.exists():
        return script_path

    raise FileNotFoundError(f"NOS script not found: {filename}")


def generate_tether_script(
    api_url: str, mac_address: str = "", poll_interval: int = 60
) -> str:
    """Generate the tether script from template.

    Loads the ONIE tether script template from the builtin_scripts directory
    and substitutes the provided parameters.

    Args:
        api_url: Base API URL for the MAAS server
        mac_address: MAC address of the management interface
        poll_interval: Seconds to wait between polling attempts

    Returns:
        The tether script as a string
    """
    script_path = _find_nos_script("onie_tether.sh")
    template = tempita.Template.from_filename(  # type: ignore[call-arg]
        str(script_path), encoding="utf-8"
    )
    return template.substitute(
        api_url=api_url,
        mac_address=mac_address,
        poll_interval=poll_interval,
        v3_api_prefix=V3_API_PREFIX,
    )


class Installer(Protocol):
    """Provides the bytes of the binary associated to an installer."""

    def bytes_stream(self) -> AsyncIterator[bytes]: ...


class InstallerEnum(Enum):
    """Installers related to a fixed set of available choices."""

    DELL = "DELL"
    SONIC = "SONIC"

    # TODO: Implement based on where the installers are.
    def bytes_stream(self) -> AsyncIterator[bytes]:
        match self:
            case InstallerEnum.DELL:

                async def gen():
                    async with aiofiles.open(
                        _SNAP_COMMON.joinpath("dell.bin"),
                        "rb",
                    ) as file:
                        while chunk := await file.read(_FIVE_MB):
                            yield chunk

                return gen()
            case InstallerEnum.SONIC:
                raise NotImplementedError
            case _:
                assert_never(self)


class InstallerFetcher(Protocol):
    """Fetches installer from some service or file storage."""

    def get_installer(self, onie_headers: OnieHeaders) -> Installer | None: ...


class EnumFetcher:
    """Fetches installer from existing, provided choices."""

    def get_installer(self, onie_headers: OnieHeaders) -> Installer | None:
        return InstallerEnum.DELL


# TODO: Add logic of how to determine the NOS
# image to use.
def choose_installer(request: Request, fetcher: InstallerFetcher) -> Installer:
    """Chooses installer based on the request and on a way to fetch them.

    The happy path is for this to just fetch the installer using the fetcher,
    which should use the request and cross-reference it with a preconfigured
    switch entry in the database to know which one to pull.

    Logic is also implemented to deal with the case of no reference to an
    existing configuration and/or inability to fetch a installer based
    on the headers.
    """
    onie_headers = OnieHeaders.from_request(request)
    if onie_headers is None:
        return InstallerEnum.DELL

    installer = fetcher.get_installer(onie_headers)
    if installer is None:
        # TODO: Logic when the user did not specify an installer.
        return InstallerEnum.DELL

    return installer


class NOSInstallerHandler(Handler):
    """NOS Installer API handler."""

    TAGS = ["Onie"]

    @handler(
        path="/tether-script",
        methods=["GET"],
        tags=TAGS,
        response_class=PlainTextResponse,
        status_code=200,
        dependencies=[],
    )
    async def get_tether_script(
        self,
        request: Request,
        services_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Serve the tether script to ONIE during initial boot.

        This endpoint:
        - Receives ONIE headers from the switch
        - Creates/updates switch entry in database
        - Returns a dynamically generated tether script

        The tether script will poll the nos-installer endpoint to download
        and install the assigned NOS when available.
        """
        onie_headers = OnieHeaders.from_request(request)
        # if onie_headers is None:
        #     raise BadRequestException("Missing or invalid ONIE headers")

        # # Extract vendor from vendor_id (format: "vendor_model" or just "vendor")
        # vendor = (
        #     onie_headers.vendor_id.split("_")[0]
        #     if onie_headers.vendor_id
        #     else None
        # )

        # # Enlist or update the switch
        # try:
        #     await services_collection.switches.enlist_or_update_switch(
        #         serial_number=onie_headers.serial_number,
        #         mac_address=onie_headers.eth_address,
        #         vendor=vendor,
        #         model=onie_headers.machine,
        #         arch=onie_headers.arch,
        #         platform=onie_headers.machine,
        #     )
        # except BadRequestException:
        #     # If there's a vendor mismatch, still serve the tether script
        #     # but the switch is already marked as broken
        #     pass

        # Generate the tether script
        # Construct the API URL from the request
        api_url = f"{request.url.scheme}://{request.url.netloc}"
        logger.info(f"API URL for tether script: {api_url}")
        script = generate_tether_script(
            api_url=api_url,
            mac_address=onie_headers.eth_address
            if onie_headers
            else "no ethernet address found",
            poll_interval=60,
        )

        return PlainTextResponse(
            content=script,
            media_type="text/x-shellscript",
            headers={
                "Content-Disposition": 'attachment; filename="maas-onie-tether.sh"',
            },
        )

    @handler(
        path="/nos-installer",
        methods=["GET"],
        tags=TAGS,
        response_model_exclude_none=True,
        dependencies=[],
    )
    async def get_nos_installer(
        self,
        request: Request,
        mac: str = "",
        services_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Serve NOS installer binary.

        This endpoint checks the switch state:
        - 'ready' state: Returns the assigned NOS installer if present
        - 'new' state: Updates heartbeat and returns empty response (no installer yet)
        - Other states: Returns empty response

        If vendor mismatch is detected, marks switch as 'broken' and returns error.

        Query parameters:
        - mac: MAC address of the switch (query parameter for BusyBox wget compatibility)
        """
        # Get MAC address from query parameter
        mac_address = mac
        if not mac_address:
            return PlainTextResponse(
                content="mac_address query parameter is required",
                status_code=400,
            )

        try:
            # Check if switch has an assigned installer
            boot_resource_id = (
                await services_collection.switches.check_installer_for_switch(
                    mac_address=mac_address
                )
            )
        except NotFoundException:
            # Switch not found - return 204 to avoid leaking information
            # about which switches are registered
            return PlainTextResponse(
                content="",
                status_code=204,  # No Content
            )

        if not boot_resource_id:
            # No installer assigned yet or switch not in correct state
            return PlainTextResponse(
                content="",
                status_code=204,  # No Content
            )

        # Get the boot resource
        try:
            boot_resource = await services_collection.boot_resources.get_by_id(
                id=boot_resource_id
            )
            if not boot_resource:
                # Boot resource not found - return 204
                return PlainTextResponse(
                    content="",
                    status_code=204,
                )

            # Get the latest complete resource set for this boot resource
            resource_set = await services_collection.boot_resource_sets.get_latest_complete_set_for_boot_resource(
                boot_resource.id
            )
            if not resource_set:
                # No complete resource set - return 204
                return PlainTextResponse(
                    content="",
                    status_code=204,
                )

            # Get the files in the resource set
            files = await services_collection.boot_resource_files.get_files_in_resource_set(
                resource_set.id
            )
            if not files:
                # No files in resource set - return 204
                return PlainTextResponse(
                    content="",
                    status_code=204,
                )
        except NotFoundException:
            # Any boot resource related lookup failed - return 204
            return PlainTextResponse(
                content="",
                status_code=204,
            )

        # Use the first file (uploaded boot resources typically have one file)
        boot_file = files[0]

        # Get the actual file path on disk
        file_path = get_bootresource_store_path() / boot_file.filename_on_disk

        # Stream the file content
        async def file_stream() -> AsyncIterator[bytes]:
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(_FIVE_MB):
                    yield chunk

        return StreamingResponse(
            content=file_stream(),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{boot_file.filename}"',
                "Content-Length": str(boot_file.size),
            },
        )

    @handler(
        path="/nos-installer/complete",
        methods=["GET"],
        tags=TAGS,
        status_code=200,
        dependencies=[],
    )
    async def mark_installation_complete_get(
        self,
        request: Request,
        mac: str = "",
        services_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Notification from tether script that installation completed successfully.

        This endpoint:
        - Receives MAC address from the tether script (query parameter)
        - Updates switch state to 'deployed'
        - Returns success message

        Query parameters:
        - mac: MAC address of the switch (for BusyBox wget compatibility)
        """
        mac_address = mac
        if not mac_address:
            return PlainTextResponse(
                content="mac query parameter is required",
                status_code=400,
            )

        try:
            switch = (
                await services_collection.switches.mark_installation_complete(
                    mac_address=mac_address
                )
            )
        except NotFoundException:
            return PlainTextResponse(
                content="Switch not found",
                status_code=404,
            )

        return PlainTextResponse(
            content=f"Installation marked complete for switch {switch.hostname or switch.id}",
            status_code=200,
        )

    @handler(
        path="/nos-installer",
        methods=["POST"],
        tags=TAGS,
        status_code=200,
        dependencies=[],
    )
    async def mark_installation_complete(
        self,
        installer_request: InstallerRequest,
        services_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Notification from tether script that installation completed successfully.

        This endpoint (POST version):
        - Receives MAC address from the tether script via JSON body
        - Updates switch state to 'deployed'
        - Returns the complete switch object
        """
        mac_address = installer_request.mac_address

        try:
            switch = (
                await services_collection.switches.mark_installation_complete(
                    mac_address=mac_address
                )
            )
        except NotFoundException:
            return PlainTextResponse(
                content="Switch not found",
                status_code=404,
            )

        return {
            "id": switch.id,
            "hostname": switch.hostname,
            "vendor": switch.vendor,
            "model": switch.model,
            "platform": switch.platform,
            "arch": switch.arch,
            "serial_number": switch.serial_number,
            "state": switch.state,
            "target_image_id": switch.target_image_id,
            "created": switch.created.isoformat() if switch.created else None,
            "updated": switch.updated.isoformat() if switch.updated else None,
        }

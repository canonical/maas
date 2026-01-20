# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
from pathlib import Path
from string import Template
from typing import Iterator

from fastapi import Depends, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError
import structlog

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.utils.images import get_bootresource_store_path
from maasserver.config import RegionConfiguration
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
    with open(script_path, "r", encoding="utf-8") as f:
        template_content = f.read()

    template = Template(template_content)
    return template.substitute(
        api_url=api_url,
        mac_address=mac_address,
        poll_interval=poll_interval,
        v3_api_prefix=V3_API_PREFIX,
    )


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
        - Returns a dynamically generated tether script

        The tether script will poll the nos-installer endpoint to download
        and install the assigned NOS when available.
        """
        onie_headers = OnieHeaders.from_request(request)

        # Generate the tether script
        # Get the configured MAAS URL from the region configuration
        with RegionConfiguration.open() as config:
            # Remove the /MAAS suffix if present, as we want just the base URL
            api_url = (
                str(config.maas_url).removesuffix("/MAAS").removesuffix("/")
            )
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

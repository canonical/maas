# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum
import os
from pathlib import Path
from typing import assert_never, AsyncIterator, Protocol

import aiofiles
from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maascommon.utils.images import get_bootresource_store_path
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.services import ServiceCollectionV3

_FIVE_MB = 5 * (2**10) * (2**10)
_SNAP_COMMON = Path(os.environ.get("SNAP_COMMON", ""))


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
        path="/onie-installer",
        methods=["GET"],
        tags=TAGS,
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[],
    )
    async def get_installer(
        self,
        request: Request,
        services_collection: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        """Serve ONIE installer binary from boot resources.

        This endpoint serves ONIE NOS installers that were uploaded via:
        maas admin boot-resources create name=onie/<vendor> architecture=<arch>/<subarch>

        The installer is looked up by querying boot resources with name format
        'onie/<vendor>' (e.g., 'onie/sonic-vs') and the architecture.
        """
        onie_headers = OnieHeaders.from_request(request)
        if onie_headers is None:
            # TODO: Handle missing ONIE headers - return error or fallback
            return {"error": "Missing ONIE headers"}

        # Determine the boot resource name from ONIE headers
        # For now, use a hardcoded example. In production, this should be
        # determined from switch configuration or ONIE vendor headers.
        boot_resource_name = "onie/sonic-vs"
        boot_resource_arch = "amd64/generic"

        # Query boot resources service for the uploaded ONIE installer
        boot_resource = await services_collection.boot_resources.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_name(
                            boot_resource_name
                        ),
                        BootResourceClauseFactory.with_architecture(
                            boot_resource_arch
                        ),
                    ]
                )
            )
        )

        if not boot_resource:
            return {"error": f"Boot resource {boot_resource_name} not found"}

        # Get the latest complete resource set for this boot resource
        resource_set = await services_collection.boot_resource_sets.get_latest_complete_set_for_boot_resource(
            boot_resource.id
        )

        if not resource_set:
            return {
                "error": f"No complete resource set found for {boot_resource_name}"
            }

        # Get the files in the resource set
        files = await services_collection.boot_resource_files.get_files_in_resource_set(
            resource_set.id
        )

        if not files:
            return {
                "error": f"No files found in resource set for {boot_resource_name}"
            }

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

# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum
import os
from pathlib import Path
from typing import assert_never, Iterator, Protocol

from fastapi import Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.responses.files import (
    FileResponse as HalFileResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.models.filestorage import FileStorage
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

    def bytes_stream(self) -> Iterator[bytes]: ...


class InstallerEnum(Enum):
    """Installers related to a fixed set of available choices."""

    DELL = "DELL"
    SONIC = "SONIC"

    # TODO: Implement based on where the installers are.
    def bytes_stream(self) -> Iterator[bytes]:
        match self:
            case InstallerEnum.DELL:
                with open(
                    _SNAP_COMMON.joinpath("dell.bin"),
                    "rb",
                ) as file:
                    while chunk := file.read(_FIVE_MB):
                        yield chunk
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
        # TODO
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            # Depends(
            # check_permissions(
            # required_roles={UserRole.USER},
            # rbac_permissions={
            # RbacPermission.VIEW,
            # RbacPermission.VIEW_ALL,
            # RbacPermission.ADMIN_MACHINES,
            # },
            # )
            # )
        ],
    )
    def get_installer(
        self,
        request: Request,
    ):
        fetcher = EnumFetcher()

        installer = choose_installer(request, fetcher)

        # accept_header = request.headers.get("Accept")
        # if accept_header == "application/hal+json":
        # return HalFileResponse.from_model(
        # installer.storage(),
        # self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
        # )
        return StreamingResponse(content=installer.bytes_stream())

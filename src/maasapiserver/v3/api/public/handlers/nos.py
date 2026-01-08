# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum
from typing import assert_never

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


class OnieHeaders(BaseModel):
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


class Installer(Enum):
    DELL = "DELL"
    SONIC = "SONIC"

    # TODO: Implement based on where the installers are.
    def storage(self) -> FileStorage:
        match self:
            case Installer.DELL:
                return FileStorage(
                    id=1000,
                    filename="dell",
                    content=bytes("test", encoding="utf8"),
                    key="1",
                    owner_id=None,
                )
            case Installer.SONIC:
                raise NotImplementedError
            case _:
                assert_never(self)


# TODO: Implement based on where the installers are.
def find_user_specified_installer(
    onie_headers: OnieHeaders,
) -> Installer | None:
    return None


# TODO: Add logic of how to determine the NOS
# image to use.
def get_installer(request: Request) -> Installer:
    onie_headers = OnieHeaders.from_request(request)
    if onie_headers is None:
        return Installer.DELL

    installer = find_user_specified_installer(onie_headers)
    if installer is None:
        # TODO: Logic when the user did not specify an installer.
        return Installer.DELL

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
        installer = get_installer(request)
        storage = installer.storage()

        def iterfile():
            yield storage.content

        accept_header = request.headers.get("Accept")

        if accept_header == "application/hal+json":
            return HalFileResponse.from_model(
                installer.storage(),
                self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
            )
        else:
            return StreamingResponse(content=iterfile())

# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum

from typing import assert_never
from fastapi import Depends, Request

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api.public.models.responses.files import FileResponse
from maasapiserver.v3.auth.base import (
    check_permissions,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.models.filestorage import FileStorage


class Installer(Enum):
    DELL = "DELL"
    SONIC = "SONIC"

    def storage(self) -> FileStorage:
        match self:
            case Installer.DELL:
                raise NotImplementedError
            case Installer.SONIC:
                raise NotImplementedError
            case _:
                assert_never(self)


def get_installer(request: Request) -> Installer:
    raise NotImplementedError


class NOSInstallerHandler(Handler):
    """NOS Installer API handler."""

    TAGS = ["Onie"]

    @handler(
        path="/onie-installer",
        methods=["GET"],
        tags=TAGS,
        # TODO
        responses={
            200: {"model": FileResponse},
        },
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
    async def stream_installer(self, request: Request) -> FileResponse:
        installer = get_installer(request)

        return FileResponse.from_model(
            installer.storage(),
            self_base_hyperlink=f"{V3_API_PREFIX}/files",
        )

# Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Optional, Self

from fastapi import Depends, Header, Response, status
from pydantic import Field

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    PreconditionFailedBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.ssh_host_keys import (
    SshHostKeyRequest,
)
from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    OPENAPI_ETAG_HEADER,
    PaginatedResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey
from maasservicelayer.services import ServiceCollectionV3


class SshHostKeyResponse(HalResponse[BaseHal]):
    kind: str = Field(default="SshHostKey")
    id: int
    created: datetime
    updated: datetime
    host: str
    key_type: str
    public_key: str
    label: Optional[str] = Field(default=None)

    @classmethod
    def from_model(
        cls, ssh_host_key: TrustedSshHostKey, self_base_hyperlink: str
    ) -> Self:
        return cls(
            id=ssh_host_key.id,
            created=ssh_host_key.created,
            updated=ssh_host_key.updated,
            host=ssh_host_key.host,
            key_type=ssh_host_key.key_type,
            public_key=ssh_host_key.public_key,
            label=ssh_host_key.label,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{ssh_host_key.id}"
                )
            ),
        )


class SshHostKeysListResponse(PaginatedResponse[SshHostKeyResponse]):
    kind: str = Field(default="SshHostKeysList")


class SshHostKeysHandler(Handler):
    """SSH Host Keys API handler."""

    TAGS = ["SshHostKeys"]

    @handler(
        path="/ssh-host-keys",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SshHostKeysListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES
                )
            )
        ],
    )
    async def list_ssh_host_keys(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SshHostKeysListResponse:
        ssh_host_keys = await services.trusted_ssh_host_keys.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        return SshHostKeysListResponse(
            items=[
                SshHostKeyResponse.from_model(
                    ssh_host_key=ssh_host_key,
                    self_base_hyperlink=f"{V3_API_PREFIX}/ssh-host-keys",
                )
                for ssh_host_key in ssh_host_keys.items
            ],
            total=ssh_host_keys.total,
            next=(
                f"{V3_API_PREFIX}/ssh-host-keys?"
                f"{pagination_params.to_next_href_format()}"
                if ssh_host_keys.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/ssh-host-keys/{ssh_host_key_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SshHostKeyResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES
                )
            )
        ],
    )
    async def get_ssh_host_key(
        self,
        ssh_host_key_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SshHostKeyResponse:
        ssh_host_key = await services.trusted_ssh_host_keys.get_by_id(
            ssh_host_key_id
        )
        if ssh_host_key is None:
            raise NotFoundException()
        response.headers["ETag"] = ssh_host_key.etag()
        return SshHostKeyResponse.from_model(
            ssh_host_key=ssh_host_key,
            self_base_hyperlink=f"{V3_API_PREFIX}/ssh-host-keys",
        )

    @handler(
        path="/ssh-host-keys",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": SshHostKeyResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES
                )
            )
        ],
    )
    async def create_ssh_host_key(
        self,
        ssh_host_key_request: SshHostKeyRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SshHostKeyResponse:
        builder = ssh_host_key_request.to_builder()
        ssh_host_key = await services.trusted_ssh_host_keys.create(builder)
        response.headers["ETag"] = ssh_host_key.etag()
        return SshHostKeyResponse.from_model(
            ssh_host_key=ssh_host_key,
            self_base_hyperlink=f"{V3_API_PREFIX}/ssh-host-keys",
        )

    @handler(
        path="/ssh-host-keys/{ssh_host_key_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
            412: {"model": PreconditionFailedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES
                )
            )
        ],
    )
    async def delete_ssh_host_key(
        self,
        ssh_host_key_id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.trusted_ssh_host_keys.delete_by_id(
            ssh_host_key_id, etag_if_match
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

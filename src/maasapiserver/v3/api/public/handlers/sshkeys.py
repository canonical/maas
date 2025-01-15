# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ConflictBodyResponse,
    NotFoundResponse,
    UnauthorizedBodyResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.sshkeys import (
    SshKeyImportFromSourceRequest,
    SshKeyManualUploadRequest,
)
from maasapiserver.v3.api.public.models.responses.sshkeys import (
    SshKeyResponse,
    SshKeysListResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.sshkeys import SshKeyClauseFactory
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3


class SshKeysHandler(Handler):
    """Ssh Keys API handler."""

    TAGS = ["SshKeys"]

    @handler(
        path="/users/me/sshkeys",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SshKeysListResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_user_sshkeys(
        self,
        token_pagination_params: TokenPaginationParams = Depends(),
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        assert authenticated_user is not None
        ssh_keys = await services.sshkeys.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=QuerySpec(
                where=SshKeyClauseFactory.with_user_id(authenticated_user.id)
            ),
        )

        return SshKeysListResponse(
            items=[
                SshKeyResponse.from_model(
                    ssh_key,
                    self_base_hyperlink=f"{V3_API_PREFIX}/users/me/sshkeys",
                )
                for ssh_key in ssh_keys.items
            ],
            next=(
                f"{V3_API_PREFIX}/users/me/sshkeys?"
                f"{TokenPaginationParams.to_href_format(ssh_keys.next_token, token_pagination_params.size)}"
                if ssh_keys.next_token
                else None
            ),
        )

    @handler(
        path="/users/me/sshkeys/{sshkey_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SshKeyResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_user_sshkey(
        self,
        sshkey_id: int,
        response: Response,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        assert authenticated_user is not None
        ssh_key = await services.sshkeys.get_one(
            query=QuerySpec(
                where=SshKeyClauseFactory.and_clauses(
                    [
                        SshKeyClauseFactory.with_id(sshkey_id),
                        SshKeyClauseFactory.with_user_id(
                            authenticated_user.id
                        ),
                    ]
                )
            ),
        )

        if not ssh_key:
            return NotFoundResponse()

        response.headers["ETag"] = ssh_key.etag()

        return SshKeyResponse.from_model(
            ssh_key,
            self_base_hyperlink=f"{V3_API_PREFIX}/users/me/sshkeys",
        )

    @handler(
        path="/users/me/sshkeys",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": SshKeyResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def create_user_sshkeys(
        self,
        sshkey_request: SshKeyManualUploadRequest,
        response: Response,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        assert authenticated_user is not None
        sshkey_request.key = (
            await services.sshkeys.normalize_openssh_public_key(
                sshkey_request.key
            )
        )
        builder = sshkey_request.to_builder(authenticated_user.id)
        created_sshkey = await services.sshkeys.create(builder.build())
        response.headers["ETag"] = created_sshkey.etag()
        return SshKeyResponse.from_model(
            created_sshkey,
            self_base_hyperlink=f"{V3_API_PREFIX}/users/me/sshkeys",
        )

    @handler(
        path="/users/me/sshkeys:import",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": SshKeysListResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
            409: {"model": ConflictBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def import_user_sshkeys(
        self,
        sshkey_request: SshKeyImportFromSourceRequest,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        assert authenticated_user is not None
        imported_sshkeys = await services.sshkeys.import_keys(
            sshkey_request.protocol,
            sshkey_request.auth_id,
            authenticated_user.id,
        )
        return SshKeysListResponse(items=imported_sshkeys)

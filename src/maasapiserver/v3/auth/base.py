# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable, Optional

from fastapi import Depends
from starlette.requests import Request

from maasapiserver.common.utils.http import extract_absolute_uri
from maasapiserver.v3.api import services
from maasapiserver.v3.auth.openapi import OpenapiOAuth2PasswordBearer
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.auth.external_auth import ExternalAuthType
from maasservicelayer.enums.rbac import RbacPermission
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ForbiddenException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    MISSING_PERMISSIONS_VIOLATION_TYPE,
    NOT_AUTHENTICATED_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import (
    AuthenticatedUser,
    RBACPermissionsPools,
)
from maasservicelayer.services import ServiceCollectionV3

# This is used just to generate the openapi spec with the security annotations.
oauth2_bearer_openapi = OpenapiOAuth2PasswordBearer(
    tokenUrl=f"{V3_API_PREFIX}/auth/login"  # pyright: ignore [reportArgumentType]
)


def get_authenticated_user(request: Request) -> AuthenticatedUser | None:
    """
    Retrieve the authenticated user from the request context.

    Returns:
        AuthenticatedUser | None: The authenticated user if available, or `None` if the request is unauthenticated.
    """
    return request.state.authenticated_user


def check_authentication() -> Callable:
    """
    Decorator to check if the request is authenticated.

    Returns:
        Callable: Decorator function that checks if the user is authenticated.
    """

    async def wrapper(request: Request) -> None:
        authenticated_user = get_authenticated_user(request)
        if not authenticated_user:
            svc: ServiceCollectionV3 = request.state.services
            external_auth_info = await svc.external_auth.get_external_auth()
            if external_auth_info:
                await svc.external_auth.raise_discharge_required_exception(
                    external_auth_info,
                    extract_absolute_uri(request),
                    request.headers,
                )

            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=NOT_AUTHENTICATED_VIOLATION_TYPE,
                        message="The endpoint requires authentication.",
                    )
                ]
            )

    return wrapper


def check_permissions(
    openfga_permission: MAASResourceEntitlement | None = None,
    rbac_permissions: Optional[set[RbacPermission]] = None,
) -> Callable:
    """
    Decorator to check if the authenticated user has the required permission to access an endpoint.

    Args:
        openfga_permission (MAASResourceEntitlement): The required entitlement on the MAAS global object to perform the operation.

        rbac_parmissions: (set[RbacPermission], optional): The set of RBAC permissions to query for the request.

    Returns:
        Callable: Decorator function that checks permissions and raises exceptions if necessary.
    """

    if not openfga_permission and not rbac_permissions:
        raise ValueError(
            "At least one of openfga_permission or rbac_permissions must be provided."
        )

    async def wrapper(
        request: Request,
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        openapi_security_generator: None = Depends(oauth2_bearer_openapi),
    ) -> AuthenticatedUser:
        """
        Wrapper function to check if the authenticated user has the required roles.

        Args:
            request (Request): The request made to the endpoint.
            user (AuthenticatedUser, optional): The authenticated user obtained from the request.
            openapi_security_generator: The OpenAPI security generator dependency. This is used only to generate the openapi
            spec accordingly.

        Returns:
            AuthenticatedUser: The authenticated user if permissions are granted.

        Raises:
            DischargeRequiredException: If the user is not authenticated and external_auth is set up.
            UnauthorizedException: If the user is not authenticated.
            ForbiddenException: If the user lacks the required roles.
        """
        external_auth_info = await services.external_auth.get_external_auth()
        if not authenticated_user:
            if external_auth_info:
                await (
                    services.external_auth.raise_discharge_required_exception(
                        external_auth_info,
                        extract_absolute_uri(request),
                        request.headers,
                    )
                )

            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=NOT_AUTHENTICATED_VIOLATION_TYPE,
                        message="The endpoint requires authentication.",
                    )
                ]
            )
        if openfga_permission and (
            not external_auth_info
            or external_auth_info.type != ExternalAuthType.RBAC
        ):
            # Check with openfga if the user has access to the resource. This is to avoid unnecessary role checks if the user doesn't have access to the resource.
            authorized = await services.openfga_tuples.get_client().has_permission_on_maas(
                openfga_permission, authenticated_user.id
            )
            if not authorized:
                raise ForbiddenException(
                    details=[
                        BaseExceptionDetail(
                            type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                            message=f"The permission '{openfga_permission}' is required.",
                        )
                    ]
                )

        if (
            external_auth_info
            and external_auth_info.type == ExternalAuthType.RBAC
        ):
            # Initialize an empty object. The permissions will be populated if the handler has requested some.
            authenticated_user.rbac_permissions = RBACPermissionsPools()
            # really pyright?
            assert authenticated_user.rbac_permissions is not None

            if rbac_permissions:
                rbac_client = await services.external_auth.get_rbac_client()
                pool_responses = await rbac_client.get_resource_pool_ids(
                    user=authenticated_user.username,
                    permissions=rbac_permissions,
                )
                all_resource_pools = set()
                # if any of the response has the access_all property, we have to fetch all the resource pools ids
                # TODO: find a better way to do this to avoid querying the db every time
                if any(r.access_all for r in pool_responses):
                    all_resource_pools = (
                        await services.resource_pools.list_ids()
                    )

                for resp in pool_responses:
                    pools = (
                        all_resource_pools
                        if resp.access_all
                        else set(resp.resources)  # pyright: ignore [reportArgumentType]
                    )
                    match resp.permission:
                        case RbacPermission.VIEW:
                            authenticated_user.rbac_permissions.visible_pools = pools
                        case RbacPermission.VIEW_ALL:
                            authenticated_user.rbac_permissions.view_all_pools = pools
                        case RbacPermission.DEPLOY_MACHINES:
                            authenticated_user.rbac_permissions.deploy_pools = pools
                        case RbacPermission.ADMIN_MACHINES:
                            authenticated_user.rbac_permissions.admin_pools = (
                                pools
                            )
                        case RbacPermission.EDIT:
                            authenticated_user.rbac_permissions.edit_pools = (
                                pools
                            )
                            if resp.access_all:
                                # The user can edit resource pools only if access_all is set
                                authenticated_user.rbac_permissions.can_edit_all_resource_pools = True
        return authenticated_user

    return wrapper

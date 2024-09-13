from typing import Callable, Optional

from fastapi import Depends
from starlette.requests import Request

from maasapiserver.common.utils.http import extract_absolute_uri
from maasapiserver.v3.api import services
from maasapiserver.v3.auth.openapi import OpenapiOAuth2PasswordBearer
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
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
    tokenUrl=f"{V3_API_PREFIX}/auth/login"
)


def get_authenticated_user(request: Request) -> AuthenticatedUser | None:
    """
    Retrieve the authenticated user from the request context.

    Returns:
        AuthenticatedUser | None: The authenticated user if available, or `None` if the request is unauthenticated.
    """
    return request.state.authenticated_user


def check_permissions(
    required_roles: set[UserRole],
    rbac_permissions: Optional[set[RbacPermission]] = None,
) -> Callable:
    """
    Decorator to check if the authenticated user has the required roles to access an endpoint.

    Args:
        required_roles (Set[UserRole]): The set of roles required to access the endpoint.
        rbac_parmissions: (set[RbacPermission], optional): The set of RBAC permissions to query for the request.

    Returns:
        Callable: Decorator function that checks permissions and raises exceptions if necessary.
    """

    async def wrapper(
        request: Request,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
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
                await services.external_auth.raise_discharge_required_exception(
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
        for role in required_roles:
            if role not in authenticated_user.roles:
                raise ForbiddenException(
                    details=[
                        BaseExceptionDetail(
                            type=MISSING_PERMISSIONS_VIOLATION_TYPE,
                            message=f"The user does not have the role '{role}' to access this endpoint.",
                        )
                    ]
                )
        if external_auth_info:
            # Initialize an empty object. The permissions will be populated if the handler has requested some.
            authenticated_user.rbac_permissions = RBACPermissionsPools()
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
                        else set(resp.resources)
                    )
                    match resp.permission:
                        case RbacPermission.VIEW:
                            authenticated_user.rbac_permissions.visible_pools = (
                                pools
                            )
                        case RbacPermission.VIEW_ALL:
                            authenticated_user.rbac_permissions.view_all_pools = (
                                pools
                            )
                        case RbacPermission.DEPLOY_MACHINES:
                            authenticated_user.rbac_permissions.deploy_pools = (
                                pools
                            )
                        case RbacPermission.ADMIN_MACHINES:
                            authenticated_user.rbac_permissions.admin_pools = (
                                pools
                            )
                        case RbacPermission.EDIT:
                            authenticated_user.rbac_permissions.edit_pools = (
                                pools
                            )
            return authenticated_user

    return wrapper

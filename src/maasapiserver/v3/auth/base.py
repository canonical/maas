# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Callable

from fastapi import Depends
from starlette.requests import Request

from maasapiserver.v3.api import services
from maasapiserver.v3.auth.openapi import OpenapiOAuth2PasswordBearer
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ForbiddenException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    MISSING_PERMISSIONS_VIOLATION_TYPE,
    NOT_AUTHENTICATED_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import AuthenticatedUser
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

    async def wrapper(
        request: Request,
        openapi_security_generator: None = Depends(oauth2_bearer_openapi),
    ) -> None:
        authenticated_user = get_authenticated_user(request)
        if not authenticated_user:
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
) -> Callable:
    """
    Decorator to check if the authenticated user has the required permission to access an endpoint.

    Args:
        openfga_permission (MAASResourceEntitlement | None): The required entitlement on the MAAS global object to
            perform the operation. If ``None``, the endpoint only requires authentication and performs its own
            authorization logic in the handler.

    Returns:
        Callable: Decorator function that checks permissions and raises exceptions if necessary.
    """

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
            UnauthorizedException: If the user is not authenticated.
            ForbiddenException: If the user lacks the required roles.
        """
        if not authenticated_user:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=NOT_AUTHENTICATED_VIOLATION_TYPE,
                        message="The endpoint requires authentication.",
                    )
                ]
            )
        if openfga_permission:
            # Check with openfga if the user has access to the resource.
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
        return authenticated_user

    return wrapper

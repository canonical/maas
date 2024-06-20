import typing

from fastapi import Depends
from pydantic import BaseModel
from starlette.requests import Request

from maasapiserver.common.models.constants import (
    MISSING_PERMISSIONS_VIOLATION_TYPE,
    NOT_AUTHENTICATED_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BaseExceptionDetail,
    ForbiddenException,
    UnauthorizedException,
)
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.auth.openapi import OpenapiOAuth2PasswordBearer
from maasapiserver.v3.constants import V3_API_PREFIX

# This is used just to generate the openapi spec with the security annotations.
oauth2_bearer_openapi = OpenapiOAuth2PasswordBearer(
    tokenUrl=f"{V3_API_PREFIX}/auth/login"
)


class AuthenticatedUser(BaseModel):
    username: str
    roles: set[UserRole]


def get_authenticated_user(request: Request) -> AuthenticatedUser | None:
    """
    Retrieve the authenticated user from the request context.

    Returns:
        AuthenticatedUser | None: The authenticated user if available, or `None` if the request is unauthenticated.
    """
    return request.state.authenticated_user


def check_permissions(required_roles: set[UserRole]) -> typing.Callable:
    """
    Decorator to check if the authenticated user has the required roles to access an endpoint.

    Args:
        required_roles (Set[UserRole]): The set of roles required to access the endpoint.

    Returns:
        Callable: Decorator function that checks permissions and raises exceptions if necessary.
    """

    def wrapper(
        authenticated_user: AuthenticatedUser
        | None = Depends(get_authenticated_user),
        openapi_security_generator: None = Depends(oauth2_bearer_openapi),
    ) -> AuthenticatedUser:
        """
        Wrapper function to check if the authenticated user has the required roles.

        Args:
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
        return authenticated_user

    return wrapper

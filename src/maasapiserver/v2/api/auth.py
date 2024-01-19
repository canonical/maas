from fastapi import Depends, HTTPException, Request, status

from maasapiserver.v2.api import services
from maasapiserver.v2.models.entities.user import User
from maasapiserver.v2.services import ServiceCollectionV2


async def authenticated_user(
    request: Request,
    services: ServiceCollectionV2 = Depends(services),
) -> User:
    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid session ID",
    )
    session_id = request.cookies.get("sessionid")
    if not session_id:
        raise unauthorized_error

    user = await services.users.get_by_session_id(session_id)
    if not user:
        raise unauthorized_error
    return user

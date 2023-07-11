from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncConnection

from ..models.v1.entities.user import User
from ..services.v1.user import UserService
from .db import db_conn


async def authenticated_user(
    request: Request,
    conn: AsyncConnection = Depends(db_conn),
) -> User:
    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid session ID",
    )
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise unauthorized_error

    service = UserService()
    user = await service.get_by_session_id(conn, session_id)
    if not user:
        raise unauthorized_error
    return user

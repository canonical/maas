#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import List, Type

from django.core import signing
from sqlalchemy import func, select, Table, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql.operators import and_, eq, gt

from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
)
from maasservicelayer.db.tables import (
    ConsumerTable,
    SessionTable,
    TokenTable,
    UserProfileTable,
    UserTable,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.users import User, UserProfile


class UserCreateOrUpdateResourceBuilder(CreateOrUpdateResourceBuilder):
    # TODO: add other fields
    def with_last_name(
        self, value: str
    ) -> "UserCreateOrUpdateResourceBuilder":
        self._request.set_value(UserTable.c.last_name.name, value)
        return self

    def with_is_active(
        self, value: bool
    ) -> "UserCreateOrUpdateResourceBuilder":
        self._request.set_value(UserTable.c.is_active.name, value)
        return self

    def with_is_superuser(
        self, value: bool
    ) -> "UserCreateOrUpdateResourceBuilder":
        self._request.set_value(UserTable.c.is_superuser.name, value)
        return self

    def with_email(self, value: str) -> "UserCreateOrUpdateResourceBuilder":
        self._request.set_value(UserTable.c.email.name, value)
        return self


class UserProfileCreateOrUpdateResourceBuilder(CreateOrUpdateResourceBuilder):
    # TODO: add other fields
    def with_auth_last_check(
        self, value: datetime
    ) -> "UserProfileCreateOrUpdateResourceBuilder":
        self._request.set_value(UserProfileTable.c.auth_last_check.name, value)
        return self


class UsersRepository(BaseRepository[User]):

    def get_repository_table(self) -> Table:
        return UserTable

    def get_model_factory(self) -> Type[User]:
        return User

    async def find_by_username(self, username: str) -> User | None:
        stmt = (
            select("*")
            .select_from(UserTable)
            .where(eq(UserTable.c.username, username))
        )
        user = (await self.connection.execute(stmt)).first()
        if not user:
            return None
        return User(**user._asdict())

    def _get_user_id(self, session_data: str) -> int | None:
        signer = signing.TimestampSigner(
            key="<UNUSED>",
            salt="django.contrib.sessions.SessionStore",
            algorithm="sha256",
        )
        details = signer.unsign_object(
            session_data, serializer=signing.JSONSerializer
        )
        user_id = details.get("_auth_user_id")
        return None if user_id is None else int(user_id)

    async def find_by_sessionid(self, sessionid: str) -> User | None:
        stmt = (
            select(
                SessionTable.c.session_data,
            )
            .select_from(SessionTable)
            .filter(
                and_(
                    eq(SessionTable.c.session_key, sessionid),
                    gt(SessionTable.c.expire_date, datetime.now(timezone.utc)),
                )
            )
        )
        row = (await self.connection.execute(stmt)).one_or_none()
        if not row:
            return None
        session_data = row[0]
        user_id = self._get_user_id(session_data)
        if not user_id:
            return None

        stmt = (
            select("*")
            .select_from(UserTable)
            .filter(eq(UserTable.c.id, user_id))
        )
        row = (await self.connection.execute(stmt)).one_or_none()
        if not row:
            return None
        return User(**row._asdict())

    async def get_user_profile(self, username: str) -> UserProfile | None:
        stmt = (
            select(UserProfileTable.columns)
            .select_from(UserProfileTable)
            .join(UserTable, eq(UserProfileTable.c.user_id, UserTable.c.id))
            .where(eq(UserTable.c.username, username))
            .limit(1)
        )
        row = (await self.connection.execute(stmt)).one_or_none()
        if not row:
            return None
        return UserProfile(**row._asdict())

    async def update_profile(
        self, user_id: int, resource: CreateOrUpdateResource
    ) -> UserProfile:
        stmt = (
            update(UserProfileTable)
            .where(eq(UserProfileTable.c.user_id, user_id))
            .returning(UserProfileTable.columns)
            .values(**resource.get_values())
        )
        try:
            updated_profile = (await self.connection.execute(stmt)).one()
        except IntegrityError:
            self._raise_already_existing_exception()
        except NoResultFound:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"User with id '{id}' does not exist.",
                    )
                ]
            )
        return UserProfile(**updated_profile._asdict())

    async def get_user_apikeys(self, username: str) -> List[str]:
        stmt = (
            select(
                func.concat(
                    ConsumerTable.c.key,
                    ":",
                    TokenTable.c.key,
                    ":",
                    TokenTable.c.secret,
                )
            )
            .select_from(TokenTable)
            .join(UserTable, eq(TokenTable.c.user_id, UserTable.c.id))
            .join(
                ConsumerTable, eq(TokenTable.c.consumer_id, ConsumerTable.c.id)
            )
            .where(
                eq(UserTable.c.username, username),
                eq(TokenTable.c.token_type, 2),  # token.ACCESS
                eq(TokenTable.c.is_approved, True),
            )
            .order_by(TokenTable.c.id)
        )

        result = (await self.connection.execute(stmt)).all()
        if not result:
            return None

        return [str(row[0]) for row in result]

from datetime import datetime

from django.core import signing
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql.operators import and_, eq, gt

from maasapiserver.common.models.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasapiserver.v3.db.base import (
    BaseRepository,
    CreateOrUpdateResource,
    CreateOrUpdateResourceBuilder,
)
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.users import User, UserProfile
from maasservicelayer.db.filters import FilterQuery
from maasservicelayer.db.tables import (
    SessionTable,
    UserProfileTable,
    UserTable,
)


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


class UserProfileCreateOrUpdateResourceBuilder(CreateOrUpdateResourceBuilder):
    # TODO: add other fields
    def with_auth_last_check(
        self, value: datetime
    ) -> "UserProfileCreateOrUpdateResourceBuilder":
        self._request.set_value(UserProfileTable.c.auth_last_check.name, value)
        return self


class UsersRepository(BaseRepository[User]):
    async def create(self, resource: CreateOrUpdateResource) -> User:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_id(self, id: int) -> User | None:
        raise NotImplementedError("Not implemented yet.")

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
                    gt(SessionTable.c.expire_date, datetime.utcnow()),
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

    async def list(
        self, token: str | None, size: int, query: FilterQuery | None = None
    ) -> ListResult[User]:
        # TODO: use the query for the filters
        pass

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

    async def update(self, id: int, resource: CreateOrUpdateResource) -> User:
        stmt = (
            update(UserTable)
            .where(eq(UserTable.c.id, id))
            .returning(UserTable.columns)
            .values(**resource.get_values())
        )
        try:
            updated_user = (await self.connection.execute(stmt)).one()
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
        return User(**updated_user._asdict())

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

    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

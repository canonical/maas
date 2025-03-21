#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, List, Type

from django.core import signing
from sqlalchemy import (
    delete,
    desc,
    distinct,
    func,
    insert,
    not_,
    Select,
    select,
    Table,
    update,
)
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.sql.operators import and_, eq, gt

from maasservicelayer.builders.users import UserProfileBuilder
from maasservicelayer.constants import SYSTEM_USERS
from maasservicelayer.context import Context
from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    ConsumerTable,
    NodeTable,
    SessionTable,
    SshKeyTable,
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
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.users import User, UserProfile, UserWithSummary
from maasservicelayer.utils.date import utcnow


class UserClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(UserTable.c.id, id))

    @classmethod
    def with_username(cls, username: str) -> Clause:
        return Clause(condition=eq(UserTable.c.username, username))


class UsersRepository(BaseRepository[User]):
    def __init__(self, context: Context):
        super().__init__(context)
        self.userprofile_mapper = DefaultDomainDataMapper(UserProfileTable)

    def get_repository_table(self) -> Table:
        return UserTable

    def get_model_factory(self) -> Type[User]:
        return User

    def select_all_statement(self) -> Select[Any]:
        return (
            select(self.get_repository_table())
            .select_from(self.get_repository_table())
            .where(not_(UserTable.c.username.in_(SYSTEM_USERS)))
        )

    async def find_by_username(self, username: str) -> User | None:
        stmt = (
            select("*")
            .select_from(UserTable)
            .where(eq(UserTable.c.username, username))
        )
        user = (await self.execute_stmt(stmt)).first()
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
                    gt(SessionTable.c.expire_date, utcnow()),
                )
            )
        )
        row = (await self.execute_stmt(stmt)).one_or_none()
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
        row = (await self.execute_stmt(stmt)).one_or_none()
        if not row:
            return None
        return User(**row._asdict())

    async def get_user_profile(self, username: str) -> UserProfile | None:
        stmt = (
            select(UserProfileTable)
            .select_from(UserProfileTable)
            .join(UserTable, eq(UserProfileTable.c.user_id, UserTable.c.id))
            .where(eq(UserTable.c.username, username))
            .limit(1)
        )
        row = (await self.execute_stmt(stmt)).one_or_none()
        if not row:
            return None
        return UserProfile(**row._asdict())

    async def create_profile(
        self, user_id: int, builder: UserProfileBuilder
    ) -> UserProfile:
        resource = self.userprofile_mapper.build_resource(builder)
        stmt = (
            insert(UserProfileTable)
            .returning(UserProfileTable)
            .values(**resource.get_values(), user_id=user_id)
        )
        try:
            profile = (await self.execute_stmt(stmt)).one()
        except IntegrityError:
            self._raise_already_existing_exception()
        return UserProfile(**profile._asdict())

    async def update_profile(
        self, user_id: int, builder: UserProfileBuilder
    ) -> UserProfile:
        resource = self.userprofile_mapper.build_resource(builder)
        stmt = (
            update(UserProfileTable)
            .where(eq(UserProfileTable.c.user_id, user_id))
            .returning(UserProfileTable)
            .values(**resource.get_values())
        )
        try:
            updated_profile = (await self.execute_stmt(stmt)).one()
        except IntegrityError:
            self._raise_already_existing_exception()
        except NoResultFound:
            raise NotFoundException(  # noqa: B904
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"User with id '{id}' does not exist.",
                    )
                ]
            )
        return UserProfile(**updated_profile._asdict())

    async def delete_profile(self, user_id: int) -> UserProfile:
        stmt = (
            delete(UserProfileTable)
            .where(eq(UserProfileTable.c.user_id, user_id))
            .returning(UserProfileTable)
        )
        deleted_profile = (await self.execute_stmt(stmt)).one()
        return UserProfile(**deleted_profile._asdict())

    async def get_user_apikeys(self, username: str) -> List[str] | None:
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

        result = (await self.execute_stmt(stmt)).all()
        if not result:
            return None

        return [str(row[0]) for row in result]

    async def delete_user_api_keys(self, user_id: int) -> None:
        consumer_stmt = (
            delete(ConsumerTable)
            .where(eq(ConsumerTable.c.user_id, user_id))
            .returning(ConsumerTable.c.id)
        )
        deleted_consumers_ids = (
            (await self.execute_stmt(consumer_stmt)).scalars().all()
        )
        token_stmt = delete(TokenTable).where(
            TokenTable.c.consumer_id.in_(deleted_consumers_ids)
        )
        await self.execute_stmt(token_stmt)

    async def list(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[User]:
        total_stmt = (
            select(func.count())
            .select_from(UserTable)
            .where(not_(UserTable.c.username.in_(SYSTEM_USERS)))
        )
        if query:
            total_stmt = query.enrich_stmt(total_stmt)
        total = (await self.execute_stmt(total_stmt)).scalar()

        stmt = (
            self.select_all_statement()
            .order_by(desc(self.get_repository_table().c.id))
            .offset((page - 1) * size)
            .limit(size)
        )
        if query:
            stmt = query.enrich_stmt(stmt)

        result = (await self.execute_stmt(stmt)).all()
        return ListResult[User](
            items=[User(**row._asdict()) for row in result],
            total=total,
        )

    async def list_with_summary(
        self, page: int, size: int
    ) -> ListResult[UserWithSummary]:
        total_stmt = (
            select(func.count())
            .select_from(UserTable)
            .where(
                and_(
                    not_(UserTable.c.username.in_(SYSTEM_USERS)),
                    eq(UserTable.c.is_active, True),
                )
            )
        )
        total = (await self.execute_stmt(total_stmt)).scalar()
        stmt = (
            select(
                UserTable.c.id,
                UserTable.c.username,
                UserTable.c.email,
                UserTable.c.is_superuser,
                UserTable.c.last_name,
                UserTable.c.last_login,
                UserProfileTable.c.completed_intro,
                UserProfileTable.c.is_local,
                func.count(distinct(NodeTable.c.id)).label("machines_count"),
                func.count(distinct(SshKeyTable.c.id)).label("sshkeys_count"),
            )
            .select_from(UserTable)
            .join(
                UserProfileTable,
                eq(UserProfileTable.c.user_id, UserTable.c.id),
            )
            .join(
                NodeTable,
                eq(NodeTable.c.owner_id, UserTable.c.id),
                isouter=True,
            )
            .join(
                SshKeyTable,
                eq(SshKeyTable.c.user_id, UserTable.c.id),
                isouter=True,
            )
            .where(
                and_(
                    not_(UserTable.c.username.in_(SYSTEM_USERS)),
                    eq(UserTable.c.is_active, True),
                )
            )
            .offset((page - 1) * size)
            .limit(size)
            .group_by(
                UserTable.c.id,
                UserTable.c.username,
                UserTable.c.email,
                UserTable.c.is_superuser,
                UserTable.c.last_name,
                UserTable.c.last_login,
                UserProfileTable.c.completed_intro,
                UserProfileTable.c.is_local,
            )
            .order_by(desc(UserTable.c.id))
        )

        result = (await self.execute_stmt(stmt)).all()
        return ListResult[UserWithSummary](
            items=[UserWithSummary(**row._asdict()) for row in result],
            total=total,
        )

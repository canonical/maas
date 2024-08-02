#  Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine


@dataclass
class DatabaseConfig:
    name: str
    host: str
    username: str | None = None
    password: str | None = None
    port: int | None = None

    @property
    def dsn(self) -> URL:
        return URL.create(
            "postgresql+asyncpg",
            host=self.host,
            port=self.port,
            database=self.name,
            username=self.username,
            password=self.password,
        )


class Database:
    def __init__(self, config: DatabaseConfig, echo: bool = False):
        self.config = config
        self.engine = create_async_engine(
            config.dsn, echo=echo, isolation_level="REPEATABLE READ"
        )

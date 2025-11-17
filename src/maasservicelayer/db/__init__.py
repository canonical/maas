#  Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
import json

from pydantic.json import pydantic_encoder
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


def custom_json_serializer(*args, **kwargs):
    return json.dumps(*args, default=pydantic_encoder, **kwargs)


class Database:
    def __init__(self, config: DatabaseConfig, echo: bool = False):
        self.config = config
        self.engine = create_async_engine(
            config.dsn,
            echo=echo,
            isolation_level="REPEATABLE READ",
            # Limit the connection pool size to 3 for the time being.
            pool_size=3,
            # Custom json serializer to handle pydantic models
            json_serializer=custom_json_serializer,
        )

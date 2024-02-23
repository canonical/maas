from sqlalchemy.ext.asyncio import create_async_engine

from maasapiserver.settings import DatabaseConfig


class Database:
    def __init__(self, config: DatabaseConfig, echo: bool = False):
        self.config = config
        self.engine = create_async_engine(
            config.dsn, echo=echo, isolation_level="REPEATABLE READ"
        )

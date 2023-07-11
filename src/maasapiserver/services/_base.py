from sqlalchemy.ext.asyncio import AsyncConnection


class Service:
    """Base class for services."""

    def __init__(self, connection: AsyncConnection):
        self.conn = connection

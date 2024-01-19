from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.services.zones import ZonesService


class ServiceCollectionV3:
    """Provide all v3 services."""

    def __init__(self, connection: AsyncConnection):
        self.zones = ZonesService(connection)

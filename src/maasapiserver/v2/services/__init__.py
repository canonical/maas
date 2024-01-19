from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v2.services.machine import MachineService
from maasapiserver.v2.services.user import UserService
from maasapiserver.v2.services.zone import ZoneService


class ServiceCollectionV2:
    """Provide all v2 services."""

    def __init__(self, connection: AsyncConnection):
        self.machines = MachineService(connection)
        self.users = UserService(connection)
        self.zones = ZoneService(connection)

from sqlalchemy.ext.asyncio import AsyncConnection

from .v1.machine import MachineService
from .v1.user import UserService
from .v1.zone import ZoneService


class ServiceCollectionV1:
    """Provide all v1 services."""

    def __init__(self, connection: AsyncConnection):
        self.machines = MachineService(connection)
        self.users = UserService(connection)
        self.zones = ZoneService(connection)

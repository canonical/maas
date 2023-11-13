from sqlalchemy.ext.asyncio import AsyncConnection

from .machine import MachineService
from .user import UserService
from .zone import ZoneService


class ServiceCollectionV2:
    """Provide all v2 services."""

    def __init__(self, connection: AsyncConnection):
        self.machines = MachineService(connection)
        self.users = UserService(connection)
        self.zones = ZoneService(connection)

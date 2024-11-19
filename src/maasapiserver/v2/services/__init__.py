#  Copyright 2023-2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v2.services.machine import MachineService
from maasapiserver.v2.services.user import UserService
from maasapiserver.v2.services.zone import ZoneService
from maasservicelayer.context import Context


class ServiceCollectionV2:
    """Provide all v2 services."""

    def __init__(self, context: Context):
        self.machines = MachineService(context)
        self.users = UserService(context)
        self.zones = ZoneService(context)

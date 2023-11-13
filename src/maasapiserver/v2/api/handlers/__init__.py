from ....common.api.base import API
from .machines import MachineHandler
from .root import RootHandler
from .zones import ZoneHandler

APIv2 = API(
    prefix="/api/v2",
    handlers=[
        RootHandler(),
        ZoneHandler(),
        MachineHandler(),
    ],
)

from ..base import API
from .machines import MachineHandler
from .root import RootHandler
from .zones import ZoneHandler

APIv1 = API(
    prefix="/api/v1",
    handlers=[
        RootHandler(),
        ZoneHandler(),
        MachineHandler(),
    ],
)

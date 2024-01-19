from maasapiserver.common.api.base import API
from maasapiserver.v2.api.handlers.machines import MachineHandler
from maasapiserver.v2.api.handlers.root import RootHandler
from maasapiserver.v2.api.handlers.zones import ZoneHandler

APIv2 = API(
    prefix="/api/v2",
    handlers=[
        RootHandler(),
        ZoneHandler(),
        MachineHandler(),
    ],
)

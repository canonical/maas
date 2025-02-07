from maasapiserver.common.api.base import API
from maasapiserver.v2.api.handlers.machines import MachineHandler
from maasapiserver.v2.api.handlers.root import RootHandler
from maasapiserver.v2.constants import V2_API_PREFIX

APIv2 = API(
    prefix=V2_API_PREFIX,
    handlers=[
        RootHandler(),
        MachineHandler(),
    ],
)

from maasapiserver.common.api.base import API
from maasapiserver.v3.api.handlers.auth import AuthHandler
from maasapiserver.v3.api.handlers.fabrics import FabricsHandler
from maasapiserver.v3.api.handlers.interfaces import InterfacesHandler
from maasapiserver.v3.api.handlers.machines import MachinesHandler
from maasapiserver.v3.api.handlers.resource_pools import ResourcePoolHandler
from maasapiserver.v3.api.handlers.root import RootHandler
from maasapiserver.v3.api.handlers.spaces import SpacesHandler
from maasapiserver.v3.api.handlers.subnets import SubnetsHandler
from maasapiserver.v3.api.handlers.users import UsersHandler
from maasapiserver.v3.api.handlers.vlans import VlansHandler
from maasapiserver.v3.api.handlers.zones import ZonesHandler
from maasapiserver.v3.constants import V3_API_PREFIX

APIv3 = API(
    prefix=V3_API_PREFIX,
    handlers=[
        RootHandler(),
        ZonesHandler(),
        ResourcePoolHandler(),
        AuthHandler(),
        MachinesHandler(),
        InterfacesHandler(),
        FabricsHandler(),
        SpacesHandler(),
        VlansHandler(),
        SubnetsHandler(),
        UsersHandler(),
    ],
)

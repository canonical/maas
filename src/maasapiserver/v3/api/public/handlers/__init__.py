#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.common.api.base import API
from maasapiserver.v3.api.public.handlers.auth import AuthHandler
from maasapiserver.v3.api.public.handlers.events import EventsHandler
from maasapiserver.v3.api.public.handlers.fabrics import FabricsHandler
from maasapiserver.v3.api.public.handlers.interfaces import InterfacesHandler
from maasapiserver.v3.api.public.handlers.machines import MachinesHandler
from maasapiserver.v3.api.public.handlers.resource_pools import (
    ResourcePoolHandler,
)
from maasapiserver.v3.api.public.handlers.root import RootHandler
from maasapiserver.v3.api.public.handlers.spaces import SpacesHandler
from maasapiserver.v3.api.public.handlers.subnets import SubnetsHandler
from maasapiserver.v3.api.public.handlers.users import UsersHandler
from maasapiserver.v3.api.public.handlers.vlans import VlansHandler
from maasapiserver.v3.api.public.handlers.zones import ZonesHandler
from maasapiserver.v3.constants import V3_API_PREFIX

APIv3 = API(
    prefix=V3_API_PREFIX,
    handlers=[
        AuthHandler(),
        EventsHandler(),
        FabricsHandler(),
        InterfacesHandler(),
        MachinesHandler(),
        ResourcePoolHandler(),
        RootHandler(),
        SpacesHandler(),
        SubnetsHandler(),
        UsersHandler(),
        VlansHandler(),
        ZonesHandler(),
    ],
)

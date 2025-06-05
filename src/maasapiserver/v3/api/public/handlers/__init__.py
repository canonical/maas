# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.common.api.base import API
from maasapiserver.v3.api.public.handlers.auth import AuthHandler
from maasapiserver.v3.api.public.handlers.configurations import (
    ConfigurationsHandler,
)
from maasapiserver.v3.api.public.handlers.discoveries import DiscoveriesHandler
from maasapiserver.v3.api.public.handlers.domains import DomainsHandler
from maasapiserver.v3.api.public.handlers.events import EventsHandler
from maasapiserver.v3.api.public.handlers.fabrics import FabricsHandler
from maasapiserver.v3.api.public.handlers.interfaces import InterfacesHandler
from maasapiserver.v3.api.public.handlers.ipranges import IPRangesHandler
from maasapiserver.v3.api.public.handlers.machines import MachinesHandler
from maasapiserver.v3.api.public.handlers.notifications import (
    NotificationsHandler,
)
from maasapiserver.v3.api.public.handlers.package_repositories import (
    PackageRepositoriesHandler,
)
from maasapiserver.v3.api.public.handlers.reservedips import ReservedIPsHandler
from maasapiserver.v3.api.public.handlers.resource_pools import (
    ResourcePoolHandler,
)
from maasapiserver.v3.api.public.handlers.root import RootHandler
from maasapiserver.v3.api.public.handlers.spaces import SpacesHandler
from maasapiserver.v3.api.public.handlers.sshkeys import SshKeysHandler
from maasapiserver.v3.api.public.handlers.sslkeys import SSLKeysHandler
from maasapiserver.v3.api.public.handlers.staticroutes import (
    StaticRoutesHandler,
)
from maasapiserver.v3.api.public.handlers.subnets import SubnetsHandler
from maasapiserver.v3.api.public.handlers.tags import TagsHandler
from maasapiserver.v3.api.public.handlers.users import UsersHandler
from maasapiserver.v3.api.public.handlers.vlans import VlansHandler
from maasapiserver.v3.api.public.handlers.zones import ZonesHandler
from maasapiserver.v3.constants import V3_API_PREFIX

APIv3 = API(
    prefix=V3_API_PREFIX,
    handlers=[
        AuthHandler(),
        ConfigurationsHandler(),
        EventsHandler(),
        DiscoveriesHandler(),
        DomainsHandler(),
        FabricsHandler(),
        InterfacesHandler(),
        IPRangesHandler(),
        MachinesHandler(),
        NotificationsHandler(),
        PackageRepositoriesHandler(),
        ReservedIPsHandler(),
        ResourcePoolHandler(),
        RootHandler(),
        StaticRoutesHandler(),
        SpacesHandler(),
        SshKeysHandler(),
        SSLKeysHandler(),
        SubnetsHandler(),
        TagsHandler(),
        UsersHandler(),
        VlansHandler(),
        ZonesHandler(),
    ],
)

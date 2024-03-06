from maasapiserver.common.api.base import API
from maasapiserver.v3.api.handlers.auth import AuthHandler
from maasapiserver.v3.api.handlers.root import RootHandler
from maasapiserver.v3.api.handlers.zones import ZonesHandler
from maasapiserver.v3.constants import V3_API_PREFIX

APIv3 = API(
    prefix=V3_API_PREFIX,
    handlers=[RootHandler(), ZonesHandler(), AuthHandler()],
)

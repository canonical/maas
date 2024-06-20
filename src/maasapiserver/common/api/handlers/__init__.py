from maasapiserver.common.api.base import API
from maasapiserver.common.api.handlers.metrics import MetricsHandler
from maasapiserver.common.api.handlers.swagger import SwaggerHandler
from maasapiserver.common.constants import API_PREFIX

APICommon = API(
    prefix=API_PREFIX,
    handlers=[
        MetricsHandler(),
        SwaggerHandler(),
    ],
)

from maasapiserver.common.api.base import API
from maasapiserver.common.api.handlers.metrics import MetricsHandler
from maasapiserver.common.api.handlers.swagger import SwaggerHandler

APICommon = API(
    prefix="",
    handlers=[
        MetricsHandler(),
        SwaggerHandler(),
    ],
)

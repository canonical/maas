from ....common.api.base import API
from .root import RootHandler

APIv3 = API(
    prefix="/api/v3",
    handlers=[
        RootHandler(),
    ],
)

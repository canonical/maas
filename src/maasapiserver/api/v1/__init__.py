from ..base import API
from .root import RootHandler

APIv1 = API(
    prefix="/api/v1",
    handlers=[
        RootHandler(),
    ],
)

from starlette.requests import Request

from maasapiserver.v3.services import ServiceCollectionV3


def services(
    request: Request,
) -> ServiceCollectionV3:
    """Dependency to return the services collection."""
    return request.state.services

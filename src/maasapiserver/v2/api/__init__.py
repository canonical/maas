from starlette.requests import Request

from maasapiserver.v2.services import ServiceCollectionV2


def services(
    request: Request,
) -> ServiceCollectionV2:
    """Dependency to return the services collection."""
    return ServiceCollectionV2(request.state.context.get_connection())

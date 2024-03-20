from maasapiserver.settings import api_prefix_path

V3_API_PREFIX = "/api/v3"
# The "/api" suffix is added by the nginx proxy. This means that the external client are making requests to "/MAAS/a/v3" and the
# nginx proxy rewrites the path to "/api/v3"
EXTERNAL_V3_API_PREFIX = api_prefix_path() + "/v3"

DEFAULT_ZONE_NAME = "default"

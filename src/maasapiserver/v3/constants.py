from maasapiserver.common.constants import API_PREFIX

V3_API_PREFIX = f"{API_PREFIX}/v3"

# THIS PREFIX MUST BE KEPT IN SYNC WITH THE NGINX RULE TO FORBID ACCESS TO THIS SET OF ENDPOINTS!
V3_INTERNAL_API_PREFIX = V3_API_PREFIX + "internal"

DEFAULT_ZONE_NAME = "default"

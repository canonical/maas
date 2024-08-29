#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.common.api.base import API
from maasapiserver.v3.api.handlers.internal.root import RootHandler
from maasapiserver.v3.constants import V3_INTERNAL_API_PREFIX

APIv3Internal = API(
    prefix=V3_INTERNAL_API_PREFIX,
    handlers=[
        RootHandler(),
    ],
)

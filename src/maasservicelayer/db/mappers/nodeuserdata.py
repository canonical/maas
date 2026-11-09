#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from base64 import b64encode

from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    CreateOrUpdateResource,
)
from maasservicelayer.models.base import ResourceBuilder


class NodeUserDataDomainDataMapper(BaseDomainDataMapper):
    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()
        for name, value in builder.populated_fields().items():
            match name:
                case "data":
                    value = b64encode(value).decode("ascii")
            resource.set_value(name, value)
        return resource

from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    CreateOrUpdateResource,
)
from maasservicelayer.models.base import ResourceBuilder


class EventDomainDataMapper(BaseDomainDataMapper):
    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()
        for name, value in builder.populated_fields().items():
            match name:
                case "type":
                    name = f"{name}_id"
                    value = value["id"]
                case "owner":
                    name = "username"

            resource.set_value(self.table_columns[name].name, value)
        return resource

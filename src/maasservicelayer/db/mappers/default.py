#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import Table

from maasservicelayer.db.mappers.base import (
    BaseDomainDataMapper,
    CreateOrUpdateResource,
)
from maasservicelayer.models.base import ResourceBuilder, Unset


class DefaultDomainDataMapper(BaseDomainDataMapper):
    """
    The domain and the data model are the same. Automatically pick the corresponding column to build the resource.
    """

    def __init__(self, table: Table):
        super().__init__(table)

    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        resource = CreateOrUpdateResource()
        for name, value in builder.dict(exclude_unset=True).items():
            if not isinstance(value, Unset):
                resource.set_value(self.table_columns[name].name, value)
        return resource

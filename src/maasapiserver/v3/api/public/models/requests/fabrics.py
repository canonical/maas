# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.db.repositories.fabrics import FabricsResourceBuilder


class FabricRequest(NamedBaseModel):
    description: Optional[str]
    class_type: Optional[str]

    def to_builder(self) -> FabricsResourceBuilder:
        return (
            FabricsResourceBuilder()
            .with_name(self.name)
            .with_description(self.description)
            .with_class_type(self.class_type)
        )

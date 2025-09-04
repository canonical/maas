# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.racks import RackBuilder


class RackRequest(NamedBaseModel):
    def to_builder(self) -> RackBuilder:
        return RackBuilder(
            name=self.name,
        )

# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.models.base import generate_builder, MaasBaseModel


@generate_builder()
class Configuration(MaasBaseModel):
    name: str
    value: Any

    def etag(self) -> str:
        pass

# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    HalResponse,
)


class ConfigurationResponse(HalResponse[BaseHal]):
    kind = "Configuration"
    name: str
    value: Any

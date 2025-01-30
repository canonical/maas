# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.enums.power_drivers import PowerTypeEnum
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Bmc(MaasTimestampedBaseModel):
    power_type: PowerTypeEnum
    power_parameters: dict

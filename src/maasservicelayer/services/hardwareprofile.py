# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.hardwareprofile import (
    HardwareProfileRepository,
)
from maasservicelayer.models.hardwareprofile import HardwareProfile
from maasservicelayer.services.base import BaseService


class HardwareProfileService(
    BaseService[
        HardwareProfile, HardwareProfileRepository, HardwareProfileBuilder
    ]
):
    resource_logging_name = "hardwareprofile"

    def __init__(
        self,
        context: Context,
        resource_pools_repository: HardwareProfileRepository,
    ):
        super().__init__(context, resource_pools_repository)

# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

from maascommon.enums.node import HardwareDeviceTypeEnum
from maascommon.enums.script import ScriptParallel, ScriptType
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Script(MaasTimestampedBaseModel):
    name: str
    title: str
    description: str
    tags: list[str] | None = None
    script_type: ScriptType
    timeout: timedelta
    destructive: bool
    default: bool
    script_id: int
    hardware_type: HardwareDeviceTypeEnum
    packages: dict
    parallel: ScriptParallel
    parameters: dict
    results: dict
    for_hardware: list[str]
    may_reboot: bool
    recommission: bool
    apply_configured_networking: bool

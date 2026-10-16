# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import datetime

from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class ScriptResult(MaasTimestampedBaseModel):
    script_set_id: int
    status: ScriptStatus
    exit_status: int | None = None
    script_name: str | None = None
    stdout: str = ""
    stderr: str = ""
    result: str = ""
    script_id: int | None = None
    script_version_id: int | None = None
    output: str = ""
    ended: datetime | None = None
    started: datetime | None = None
    parameters: dict
    physical_blockdevice_id: int | None = None
    suppressed: bool = False
    interface_id: int | None = None

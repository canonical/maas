# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maascommon.enums.scriptresult import ScriptStatus
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class ScriptResult(MaasTimestampedBaseModel):
    # TODO: model to be completed.
    script_set_id: int
    status: ScriptStatus
    stdout: str = ""
    stderr: str = ""
    result: str = ""
    output: str = ""
    parameters: str = "{}"
    suppressed: bool = False

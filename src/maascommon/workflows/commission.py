#  Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import Any

# Workflows names
COMMISSION_N_WORKFLOW_NAME = "CommissionNWorkflow"
COMMISSION_WORKFLOW_NAME = "commission"


# Workflows parameters
@dataclass
class CommissionParam:
    system_id: str
    enable_ssh: bool = False
    skip_bmc_config: bool = False
    skip_networking: bool = False
    skip_storage: bool = False
    commissioning_scripts: list[str] | None = None
    testing_scripts: list[str] | None = None
    script_input: dict[str, dict[str, Any]] | None = None


@dataclass
class CommissionResult:
    system_id: str
    status: str

@dataclass
class CommissionNParam:
    params: list[CommissionParam]

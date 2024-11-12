#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

# Workflows names
COMMISSION_N_WORKFLOW_NAME = "CommissionNWorkflow"
COMMISSION_WORKFLOW_NAME = "commission"


# Workflows parameters
@dataclass
class CommissionParam:
    system_id: str
    queue: str


@dataclass
class CommissionNParam:
    params: list[CommissionParam]

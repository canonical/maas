#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from maascommon.constants import NODE_TIMEOUT
from maascommon.workflows.power import PowerParam

DEPLOY_MANY_WORKFLOW_NAME = "deploy-many"
DEPLOY_WORKFLOW_NAME = "deploy"


# Workflows parameters
@dataclass
class DeployParam:
    system_id: str
    ephemeral_deploy: bool
    can_set_boot_order: bool
    task_queue: str
    power_params: PowerParam
    timeout: int = 2 * NODE_TIMEOUT


@dataclass
class DeployManyParam:
    params: list[DeployParam]


# Workflows results
@dataclass
class DeployResult:
    system_id: str
    success: bool

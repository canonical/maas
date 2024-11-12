#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from maascommon.workflows.power import PowerParam

DEPLOY_N_WORKFLOW_NAME = "deploy-n"
DEPLOY_WORKFLOW_NAME = "deploy"


# Workflows parameters
@dataclass
class DeployParam:
    system_id: str
    ephemeral_deploy: bool
    can_set_boot_order: bool
    task_queue: str
    power_params: PowerParam


@dataclass
class DeployNParam:
    params: list[DeployParam]


# Workflows results
@dataclass
class DeployResult:
    system_id: str
    success: bool

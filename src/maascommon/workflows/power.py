#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from enum import Enum
from typing import Any

# Workflows names
POWER_ON_WORKFLOW_NAME = "power-on"
POWER_CYCLE_WORKFLOW_NAME = "power-cycle"
POWER_OFF_WORKFLOW_NAME = "power-off"
POWER_QUERY_WORKFLOW_NAME = "power-query"
POWER_MANY_WORKFLOW_NAME = "power-many"
POWER_RESET_WORKFLOW_NAME = "power-reset"


# XXX: Once Python 3.11 switch to StrEnum
class PowerAction(Enum):
    POWER_ON = POWER_ON_WORKFLOW_NAME
    POWER_OFF = POWER_OFF_WORKFLOW_NAME
    POWER_CYCLE = POWER_CYCLE_WORKFLOW_NAME
    POWER_QUERY = POWER_QUERY_WORKFLOW_NAME
    POWER_RESET = POWER_RESET_WORKFLOW_NAME


# Workflows parameters
@dataclass
class PowerParam:
    system_id: str

    # XXX: should be removed, once we can fetch everything by system_id
    # inside workflow itself and pass to the underlying PowerOn activity.
    driver_type: str
    driver_opts: dict[str, Any]
    task_queue: str
    is_dpu: bool


@dataclass
class PowerOnParam(PowerParam):
    """
    Parameters required by the PowerOn workflow
    """

    pass


@dataclass
class PowerCycleParam(PowerParam):
    """
    Parameters required by the PowerCycle workflow
    """

    pass


@dataclass
class PowerQueryParam(PowerParam):
    """

    Parameters required by the PowerQuery workflow
    """

    pass


@dataclass
class PowerOffParam(PowerParam):
    """
    Parameters required by the PowerOff workflow
    """

    pass


@dataclass
class PowerManyParam:
    """
    Parameters required by the PowerMany workflow
    """

    action: str
    # XXX: params property should be removed, once we can fetch everything by system_id
    # change to list[str] (list of system_ids)
    params: list[PowerParam]


@dataclass
class PowerResetParam(PowerParam):
    """
    Parameters required by the PowerReset workflow
    """

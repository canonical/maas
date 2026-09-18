#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

# Workflows names
POWER_ON_WORKFLOW_NAME = "power-on"
POWER_CYCLE_WORKFLOW_NAME = "power-cycle"
POWER_OFF_WORKFLOW_NAME = "power-off"
POWER_QUERY_WORKFLOW_NAME = "power-query"
POWER_MANY_WORKFLOW_NAME = "power-many"
POWER_RESET_WORKFLOW_NAME = "power-reset"

# Activity names
# The set-boot-order activity is executed on the agent (same as the power
# activities); the power workflows dispatch it when a boot order is supplied.
SET_BOOT_ORDER_ACTIVITY_NAME = "set-boot-order"


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

    # Optional serialized boot order (list of device dicts). When present, the
    # power workflow applies it via the agent 'set-boot-order' activity before
    # the power action, so boot ordering rides the Temporal path instead of the
    # legacy region RPC. Defaults to None so existing callers are unaffected.
    boot_order: Optional[list[dict[str, Any]]] = None


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


@dataclass
class SetBootOrderParam:
    """
    Parameters required by the set-boot-order activity (run on the agent).
    """

    system_id: str
    power_params: PowerParam
    order: list[dict[str, Any]]

# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Union

from pydantic import Field

from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.power import PowerState
from maasservicelayer.models.base import ResourceBuilder, UNSET, Unset


class NodeBuilder(ResourceBuilder):
    """Autogenerated from utilities/generate_builders.py.

    You can still add your custom methods here, they won't be overwritten by
    the generated code.
    """

    created: Union[datetime, Unset] = Field(default=UNSET, required=False)
    current_commissioning_script_set_id: Union[int, None, Unset] = Field(
        default=UNSET, required=False
    )
    current_installation_script_set_id: Union[int, None, Unset] = Field(
        default=UNSET, required=False
    )
    current_testing_script_set_id: Union[int, None, Unset] = Field(
        default=UNSET, required=False
    )
    error_description: Union[str, Unset] = Field(default=UNSET, required=False)
    hostname: Union[str, Unset] = Field(default=UNSET, required=False)
    id: Union[int, Unset] = Field(default=UNSET, required=False)
    node_type: Union[NodeTypeEnum, Unset] = Field(
        default=UNSET, required=False
    )
    owner_id: Union[int, None, Unset] = Field(default=UNSET, required=False)
    power_state: Union[PowerState, Unset] = Field(
        default=UNSET, required=False
    )
    power_state_updated: Union[datetime, None, Unset] = Field(
        default=UNSET, required=False
    )
    status: Union[NodeStatus, Unset] = Field(default=UNSET, required=False)
    system_id: Union[str, Unset] = Field(default=UNSET, required=False)
    updated: Union[datetime, Unset] = Field(default=UNSET, required=False)

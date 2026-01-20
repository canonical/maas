# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Union

from pydantic import Field

from maasservicelayer.models.base import ResourceBuilder, UNSET, Unset


class SwitchBuilder(ResourceBuilder):
    """Builder for Switch model."""

    created: Union[datetime, Unset] = Field(default=UNSET, required=False)
    updated: Union[datetime, Unset] = Field(default=UNSET, required=False)
    target_image_id: Union[int, None, Unset] = Field(
        default=UNSET, required=False
    )


class SwitchInterfaceBuilder(ResourceBuilder):
    """Builder for SwitchInterface model."""

    created: Union[datetime, Unset] = Field(default=UNSET, required=False)
    updated: Union[datetime, Unset] = Field(default=UNSET, required=False)
    mac_address: Union[str, Unset] = Field(default=UNSET, required=False)
    switch_id: Union[int, Unset] = Field(default=UNSET, required=False)

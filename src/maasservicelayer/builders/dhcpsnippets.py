# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Union

from pydantic import Field

from maasservicelayer.models.base import ResourceBuilder, UNSET, Unset


class DhcpSnippetBuilder(ResourceBuilder):
    """Autogenerated from utilities/generate_builders.py.

    You can still add your custom methods here, they won't be overwritten by
    the generated code.
    """

    created: Union[datetime, Unset] = Field(default=UNSET, required=False)
    description: Union[str, Unset] = Field(default=UNSET, required=False)
    enabled: Union[bool, Unset] = Field(default=UNSET, required=False)
    id: Union[int, Unset] = Field(default=UNSET, required=False)
    iprange_id: Union[int, Unset] = Field(default=UNSET, required=False)
    name: Union[str, Unset] = Field(default=UNSET, required=False)
    node_id: Union[int, Unset] = Field(default=UNSET, required=False)
    subnet_id: Union[int, Unset] = Field(default=UNSET, required=False)
    updated: Union[datetime, Unset] = Field(default=UNSET, required=False)
    value_id: Union[int, None, Unset] = Field(default=UNSET, required=False)

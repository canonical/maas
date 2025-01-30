# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from typing import Union

from pydantic import Field

from maasservicelayer.models.base import ResourceBuilder, UNSET, Unset


class UserBuilder(ResourceBuilder):
    """Autogenerated from utilities/generate_builders.py.

    You can still add your custom methods here, they won't be overwritten by
    the generated code.
    """

    date_joined: Union[datetime, Unset] = Field(default=UNSET, required=False)
    email: Union[str, None, Unset] = Field(default=UNSET, required=False)
    first_name: Union[str, Unset] = Field(default=UNSET, required=False)
    id: Union[int, Unset] = Field(default=UNSET, required=False)
    is_active: Union[bool, Unset] = Field(default=UNSET, required=False)
    is_staff: Union[bool, Unset] = Field(default=UNSET, required=False)
    is_superuser: Union[bool, Unset] = Field(default=UNSET, required=False)
    last_login: Union[datetime, None, Unset] = Field(
        default=UNSET, required=False
    )
    last_name: Union[str, None, Unset] = Field(default=UNSET, required=False)
    password: Union[str, Unset] = Field(default=UNSET, required=False)
    username: Union[str, Unset] = Field(default=UNSET, required=False)


class UserProfileBuilder(ResourceBuilder):
    """Autogenerated from utilities/generate_builders.py.

    You can still add your custom methods here, they won't be overwritten by
    the generated code.
    """

    auth_last_check: Union[datetime, None, Unset] = Field(
        default=UNSET, required=False
    )
    completed_intro: Union[bool, Unset] = Field(default=UNSET, required=False)
    id: Union[int, Unset] = Field(default=UNSET, required=False)
    is_local: Union[bool, Unset] = Field(default=UNSET, required=False)
    user_id: Union[int, Unset] = Field(default=UNSET, required=False)

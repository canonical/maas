#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
from typing import Any, Optional

from pydantic import BaseModel, Field, root_validator, validator

from maasservicelayer.auth.macaroons.models.base import Resource


class UserDetailsResponse(BaseModel):
    username: str
    fullname: Optional[str] = Field(validation_alias="name")
    email: Optional[str]


class ValidateUserResponse(UserDetailsResponse):
    active: bool
    superuser: bool


class GetGroupsResponse(BaseModel):
    groups: Sequence[str]


class ResourceListResponse(BaseModel):
    resources: Sequence[Resource]


class UpdateResourcesResponse(BaseModel):
    sync_id: str = Field(alias="sync-id")


class PermissionResourcesMapping(BaseModel):
    """
    This class is related to the rbac allowed-for-user endpoint response.
    The response we get from that api call is in the form of:
        {"<permission1>": [""], # this means all the resources
         "<permission2>": ["1","2","3"]}
    The attributes `resources` and `access_all` are mutually exclusive:
        - if we can access all the resources we don't have the resource ids
        - if we can't access all the resources we have the resource ids
    When creating the class, you should not populate the `access_all` attribute
    as there are validators in place to assign it the correct value.
    """

    permission: str
    resources: Optional[Sequence[int]]
    access_all: bool = False

    @validator("resources", pre=True)
    def preprocess_resources(cls, data: Optional[Sequence[str]]):
        if data == [""] or data is None:
            return None
        else:
            return [int(id) for id in data]

    # TODO: switch to model_validator when we migrate to pydantic 2.x
    @root_validator(pre=False)
    def populate_access_all_property(cls, values: dict[str, Any]):
        if values["resources"] is None:
            values["access_all"] = True
        return values


class AllowedForUserResponse(BaseModel):
    permissions: Sequence[PermissionResourcesMapping]

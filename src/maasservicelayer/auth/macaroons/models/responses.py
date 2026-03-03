#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from maasservicelayer.auth.macaroons.models.base import Resource
from maasservicelayer.enums.rbac import RbacPermission


class UserDetailsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    username: str
    fullname: Optional[str] = Field(validation_alias="name")
    email: Optional[str]


class ValidateUserResponse(UserDetailsResponse):
    active: bool
    superuser: bool


class GetGroupsResponse(BaseModel):
    groups: Sequence[str]


class ResourceListResponse(BaseModel):
    resources: list[Resource]


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

    permission: RbacPermission
    resources: Optional[list[int]] = None
    access_all: bool = False

    @field_validator("resources", mode="before")
    @classmethod
    def preprocess_resources(cls, data: Optional[list[str]]) -> Optional[list[int]]:
        if data == [""] or data is None:
            return None
        return [int(id) for id in data]

    @model_validator(mode="after")
    def populate_access_all_property(self) -> "PermissionResourcesMapping":
        if self.resources is None:
            self.access_all = True
        return self
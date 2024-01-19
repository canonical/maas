from typing import Optional

from pydantic import BaseModel

from maasapiserver.v2.models.entities.machine import Machine


class MachineListGroupResponse(BaseModel):
    name: Optional[str]
    value: Optional[str]
    count: Optional[int]
    collapsed: Optional[bool]
    items: Optional[list[Machine]]


class MachineListResponse(BaseModel):
    count: int
    cur_page: int
    num_pages: int
    groups: Optional[list[MachineListGroupResponse]]

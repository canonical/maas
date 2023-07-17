from typing import Optional

from pydantic import BaseModel


class MachineRequest(BaseModel):
    id: int
    actions: list[str]
    permissions: list[str]


class MachineListGroupRequest(BaseModel):
    name: Optional[str]
    value: Optional[str]
    count: Optional[int]
    collapsed: Optional[bool]
    items: list[MachineRequest]


class MachineListRequest(BaseModel):
    count: int
    cur_page: int
    num_pages: int
    groups: list[MachineListGroupRequest]

from datetime import datetime

from pydantic import BaseModel


class Zone(BaseModel):
    """An availability zone."""

    id: int
    created: datetime
    updated: datetime
    name: str
    description: str
    devices_count: int
    machines_count: int
    controllers_count: int

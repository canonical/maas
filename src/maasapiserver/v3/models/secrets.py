from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Secret(BaseModel):
    created: datetime
    updated: datetime
    path: str
    value: Any

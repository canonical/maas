from typing import Any

from pydantic import BaseModel


class Configuration(BaseModel):
    id: int
    name: str
    value: Any

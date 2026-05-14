#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel


class DriverRegisterRequest(BaseModel):
    """Request body for a single driver registration."""

    name: str
    version: str
    schema: dict[str, Any]


class DriverRegisterBody(BaseModel):
    """Request body containing multiple drivers to register."""

    drivers: list[DriverRegisterRequest]

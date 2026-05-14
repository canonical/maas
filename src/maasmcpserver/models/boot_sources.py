# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel
from pydantic.config import ConfigDict


class BootSourceSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    os: str | None = None
    release: str | None = None
    arches: list[str]
    subarches: list[str]
    labels: list[str]


class BootSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    url: str
    keyring_data: str | None = None
    selections: list[BootSourceSelection]

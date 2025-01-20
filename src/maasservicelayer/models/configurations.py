# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from pydantic import BaseModel

from maasservicelayer.models.base import make_builder


class Configuration(BaseModel):
    id: int
    name: str
    value: Any


ConfigurationBuilder = make_builder(Configuration)

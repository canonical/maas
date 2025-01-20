#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import Table

from maasservicelayer.models.base import ResourceBuilder


class CreateOrUpdateResource(dict):
    def get_values(self) -> dict[str, Any]:
        return self

    def set_value(self, key: str, value: Any) -> None:
        self[key] = value


class BaseDomainDataMapper(ABC):
    """
    How the domain model should map to the data model.
    """

    def __init__(self, table: Table):
        self.table_columns = {
            column_name: column for column_name, column in table.c.items()
        }

    @abstractmethod
    def build_resource(
        self, builder: ResourceBuilder
    ) -> CreateOrUpdateResource:
        pass

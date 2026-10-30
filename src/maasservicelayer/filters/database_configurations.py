# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.configurations import DatabaseConfiguration


class DatabaseConfigurationsFilters(FilterFactory):
    model = DatabaseConfiguration

    @classmethod
    def with_name(cls, name: str) -> FieldFilter:
        return cls._equals("name", name)

    @classmethod
    def with_names(cls, names: set[str]) -> FieldFilter:
        return cls._is_in("name", names)

# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync


class BootResourceFileSyncFilters(FilterFactory):
    model = BootResourceFileSync

    @classmethod
    def with_file_id(cls, file_id: int) -> FieldFilter:
        return cls._equals("file_id", file_id)

    @classmethod
    def with_file_ids(cls, file_ids: set[int]) -> FieldFilter:
        return cls._is_in("file_id", file_ids)

#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.filestorage import FileStorage


@dataclass(frozen=True)
class FileStorageFilenamePrefixFilter(CustomFilter):
    model: ClassVar[type[FileStorage]] = FileStorage
    prefix: str


class FileStorageFilters(FilterFactory):
    model = FileStorage

    @classmethod
    def with_filename(cls, filename: str) -> FieldFilter:
        return cls._equals("filename", filename)

    @classmethod
    def with_filename_prefix(
        cls, prefix: str
    ) -> FileStorageFilenamePrefixFilter:
        return FileStorageFilenamePrefixFilter(prefix)

    @classmethod
    def with_key(cls, key: str) -> FieldFilter:
        return cls._equals("key", key)

    @classmethod
    def with_owner_id(cls, owner_id: int) -> FieldFilter:
        return cls._equals("owner_id", owner_id)

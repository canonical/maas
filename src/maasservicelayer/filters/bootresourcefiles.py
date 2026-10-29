# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from typing import ClassVar

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.bootresourcefiles import BootResourceFile


@dataclass(frozen=True)
class BootResourceFileSHA256Prefix(CustomFilter):
    model: ClassVar = BootResourceFile
    partial_sha256: str


@dataclass(frozen=True)
class BootResourceFilesOfResources(CustomFilter):
    model: ClassVar = BootResourceFile
    resource_ids: tuple[int, ...]


class BootResourceFileFilters(FilterFactory):
    model = BootResourceFile

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_sha256_starting_with(
        cls, partial_sha256: str
    ) -> BootResourceFileSHA256Prefix:
        return BootResourceFileSHA256Prefix(partial_sha256)

    @classmethod
    def with_sha256(cls, sha256: str) -> FieldFilter:
        return cls._equals("sha256", sha256)

    @classmethod
    def with_sha256_in(cls, sha256_list: list[str]) -> FieldFilter:
        return cls._is_in("sha256", sha256_list)

    @classmethod
    def with_resource_set_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("resource_set_id", ids)

    @classmethod
    def with_resource_set_id(cls, id: int) -> FieldFilter:
        return cls._equals("resource_set_id", id)

    @classmethod
    def with_boot_resource_ids(
        cls, ids: list[int]
    ) -> BootResourceFilesOfResources:
        return BootResourceFilesOfResources(tuple(ids))

    @classmethod
    def with_boot_resource_id(cls, id: int) -> BootResourceFilesOfResources:
        return BootResourceFilesOfResources((id,))

    @classmethod
    def with_filename(cls, filename: str) -> FieldFilter:
        return cls._equals("filename", filename)

    @classmethod
    def with_filetype(cls, filetype: BootResourceFileType) -> FieldFilter:
        return cls._equals("filetype", filetype)

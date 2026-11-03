# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.db.mappers.base import StorageRow
from maasservicelayer.models.bootsources import (
    BootSourceAvailableImage,
    BootSourceCacheOSRelease,
)


class BootSourceAvailableImageDataMapper:
    def to_domain(self, row: StorageRow) -> BootSourceAvailableImage:
        return BootSourceAvailableImage(**row)

    def to_domain_for_boot_source(
        self, row: StorageRow, boot_source_id: int
    ) -> BootSourceAvailableImage:
        return self.to_domain({**row, "boot_source_id": boot_source_id})


class BootSourceCacheOSReleaseDataMapper:
    def to_domain(self, row: StorageRow) -> BootSourceCacheOSRelease:
        return BootSourceCacheOSRelease(**row)

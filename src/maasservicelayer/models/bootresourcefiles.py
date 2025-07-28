# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.utils.image_local_files import LocalBootResourceFile


@generate_builder()
class BootResourceFile(MaasTimestampedBaseModel):
    filename: str
    filetype: BootResourceFileType
    extra: dict
    sha256: str
    size: int
    filename_on_disk: str
    largefile_id: int | None = None
    resource_set_id: int | None = None

    def create_local_file(self) -> LocalBootResourceFile:
        return LocalBootResourceFile(
            self.sha256, self.filename_on_disk, self.size
        )

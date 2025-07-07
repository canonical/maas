# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.boot_resources import BootResourceFileType
from maasservicelayer.db.tables import BootResourceFileTable
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootresourcefile_entry(
    fixture: Fixture,
    filename: str,
    filetype: BootResourceFileType,
    sha256: str,
    size: int,
    filename_on_disk: str,
    resource_set_id: int,
    largefile_id: int | None = None,
    **extra_details,
) -> BootResourceFile:
    now = utcnow()

    file = {
        "created": now,
        "updated": now,
        "filename": filename,
        "filetype": filetype,
        "sha256": sha256,
        "size": size,
        "filename_on_disk": filename_on_disk,
        "resource_set_id": resource_set_id,
        "largefile_id": largefile_id,
        "extra": {},
    }
    file.update(extra_details)

    [created] = await fixture.create(BootResourceFileTable.name, file)
    return BootResourceFile(**created)

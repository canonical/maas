# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.tables import BootResourceFileSyncTable
from maasservicelayer.models.bootresourcefilesync import BootResourceFileSync
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootresourcefilesync_entry(
    fixture: Fixture, size: int, file_id: int, region_id: int
) -> BootResourceFileSync:
    now = utcnow()
    filesync = {
        "created": now,
        "updated": now,
        "size": size,
        "file_id": file_id,
        "region_id": region_id,
    }

    [created] = await fixture.create(BootResourceFileSyncTable.name, filesync)
    return BootResourceFileSync(**created)

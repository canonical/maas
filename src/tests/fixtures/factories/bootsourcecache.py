# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.tables import BootSourceCacheTable
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootsourcecache_entry(
    fixture: Fixture,
    boot_source_id: int,
    os: str,
    arch: str,
    subarch: str,
    release: str,
    **extra_details,
) -> BootSourceCache:
    now = utcnow()
    bootsourcecache = {
        "created": now,
        "updated": now,
        "os": os,
        "arch": arch,
        "subarch": subarch,
        "release": release,
        "label": "stable",
        "extra": {},
        "boot_source_id": boot_source_id,
    }

    bootsourcecache.update(extra_details)

    [created] = await fixture.create(
        BootSourceCacheTable.name, bootsourcecache
    )

    return BootSourceCache(**created)

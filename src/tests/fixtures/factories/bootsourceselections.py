# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.db.tables import BootSourceSelectionTable
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootsourceselection_entry(
    fixture: Fixture,
    os: str,
    release: str,
    arch: str,
    boot_source_id: int,
) -> BootSourceSelection:
    now = utcnow()

    selection = {
        "created": now,
        "updated": now,
        "os": os,
        "release": release,
        "arch": arch,
        "boot_source_id": boot_source_id,
    }

    [created] = await fixture.create(BootSourceSelectionTable.name, selection)

    return BootSourceSelection(**created)

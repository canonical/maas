# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.db.tables import (
    BootSourceSelectionLegacyTable,
    BootSourceSelectionTable,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_legacybootsourceselection_entry(
    fixture: Fixture,
    os: str,
    release: str,
    arches: list[str],
    boot_source_id: int,
) -> BootSourceSelection:
    now = utcnow()

    selection = {
        "created": now,
        "updated": now,
        "os": os,
        "release": release,
        "arches": arches,
        "subarches": ["*"],
        "labels": ["*"],
        "boot_source_id": boot_source_id,
    }

    [created] = await fixture.create(
        BootSourceSelectionLegacyTable.name, selection
    )

    return LegacyBootSourceSelection(**created)


async def create_test_bootsourceselection_entry(
    fixture: Fixture,
    os: str,
    release: str,
    arch: str,
    boot_source_id: int,
    legacy_selection: LegacyBootSourceSelection | None = None,
) -> BootSourceSelection:
    now = utcnow()

    if not legacy_selection:
        legacy_selection = await create_test_legacybootsourceselection_entry(
            fixture, os, release, [arch], boot_source_id
        )

    selection = {
        "created": now,
        "updated": now,
        "os": os,
        "release": release,
        "arch": arch,
        "boot_source_id": boot_source_id,
        "legacyselection_id": legacy_selection.id,
    }

    [created] = await fixture.create(BootSourceSelectionTable.name, selection)

    return BootSourceSelection(**created)

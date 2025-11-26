# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.db.tables import BootResourceTable
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootresource_entry(
    fixture: Fixture,
    rtype: BootResourceType,
    name: str,
    architecture: str,
    selection_id: int | None = None,
    **extra_details,
) -> BootResource:
    now = utcnow()
    bootresource = {
        "created": now,
        "updated": now,
        "rtype": rtype,
        "name": name,
        "architecture": architecture,
        "base_image": "",
        "rolling": False,
        "selection_id": selection_id,
        "extra": {},
    }

    bootresource.update(extra_details)

    [created_bootresource] = await fixture.create(
        BootResourceTable.name, bootresource
    )
    return BootResource(**created_bootresource)

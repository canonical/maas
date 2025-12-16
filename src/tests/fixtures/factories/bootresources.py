# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
    ImageStatus,
)
from maasservicelayer.db.tables import BootResourceTable
from maasservicelayer.models.bootresources import (
    BootResource,
    CustomBootResourceStatus,
)
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresourcefilesync import (
    create_test_bootresourcefilesync_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.fixtures.factories.node import create_test_region_controller_entry
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


async def create_test_custom_bootresource_status_entry(
    fixture: Fixture,
    name: str,
    architecture: str,
    file_size: int = 1024,
    sync_size: int = 1024,
    region_controller: dict | None = None,
) -> CustomBootResourceStatus:
    boot_resource = await create_test_bootresource_entry(
        fixture,
        rtype=BootResourceType.UPLOADED,
        name=name,
        architecture=architecture,
    )

    boot_resource_set = await create_test_bootresourceset_entry(
        fixture,
        version="1",
        label="stable",
        resource_id=boot_resource.id,
    )

    boot_resource_file = await create_test_bootresourcefile_entry(
        fixture,
        filename="file",
        filetype=BootResourceFileType.ROOT_TGZ,
        sha256="abc123",
        size=file_size,
        filename_on_disk="file",
        resource_set_id=boot_resource_set.id,
    )

    if region_controller is None:
        region_controller = await create_test_region_controller_entry(fixture)

    await create_test_bootresourcefilesync_entry(
        fixture,
        size=sync_size,
        file_id=boot_resource_file.id,
        region_id=region_controller["id"],
    )

    if sync_size == file_size:
        status = ImageStatus.READY
    elif sync_size == 0:
        status = ImageStatus.WAITING_FOR_DOWNLOAD
    else:
        status = ImageStatus.DOWNLOADING

    return CustomBootResourceStatus(
        id=boot_resource.id,
        status=status,
        sync_percentage=(sync_size / file_size) * 100,
    )

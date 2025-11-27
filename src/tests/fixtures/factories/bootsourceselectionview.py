# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
    ImageStatus,
    ImageUpdateStatus,
)
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelectionStatus,
)
from tests.fixtures.factories.boot_sources import create_test_bootsource_entry
from tests.fixtures.factories.bootresourcefiles import (
    create_test_bootresourcefile_entry,
)
from tests.fixtures.factories.bootresourcefilesync import (
    create_test_bootresourcefilesync_entry,
)
from tests.fixtures.factories.bootresources import (
    create_test_bootresource_entry,
)
from tests.fixtures.factories.bootresourcesets import (
    create_test_bootresourceset_entry,
)
from tests.fixtures.factories.bootsourcecache import (
    create_test_bootsourcecache_entry,
)
from tests.fixtures.factories.bootsourceselections import (
    create_test_bootsourceselection_entry,
)
from tests.fixtures.factories.node import create_test_region_controller_entry
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_selection_status_entry(
    fixture: Fixture,
    os: str = "ubuntu",
    release: str = "noble",
    arch: str = "amd64",
    subarch: str = "generic",
    boot_source: BootSource | None = None,
    region_controller: dict | None = None,
    cache_version: str = "1",
    set_version: str = "1",
    file_size: int = 1024,
    sync_size: int = 1024,
) -> BootSourceSelectionStatus:
    if boot_source is None:
        boot_source = await create_test_bootsource_entry(
            fixture,
            name="test-boot_source",
            url="http://example.com",
            priority=1,
        )
    await create_test_bootsourcecache_entry(
        fixture,
        boot_source_id=boot_source.id,
        os=os,
        arch=arch,
        subarch=subarch,
        release=release,
        latest_version=cache_version,
        kflavor="generic",
    )
    selection = await create_test_bootsourceselection_entry(
        fixture,
        os=os,
        release=release,
        arch=arch,
        boot_source_id=boot_source.id,
    )
    boot_resource = await create_test_bootresource_entry(
        fixture,
        rtype=BootResourceType.SYNCED,
        name=f"{os}/{release}",
        architecture=f"{arch}/{subarch}",
        selection_id=selection.id,
        kflavor="generic",
    )

    boot_resource_set = await create_test_bootresourceset_entry(
        fixture,
        version=set_version,
        label="stable",
        resource_id=boot_resource.id,
    )

    boot_resource_file = await create_test_bootresourcefile_entry(
        fixture,
        filename="file",
        filetype=BootResourceFileType.SQUASHFS_IMAGE,
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

    if sync_size == 0:
        status = ImageStatus.WAITING_FOR_DOWNLOAD
    elif sync_size < file_size:
        status = ImageStatus.DOWNLOADING
    else:
        status = ImageStatus.READY

    if set_version >= cache_version:
        update_status = ImageUpdateStatus.NO_UPDATES_AVAILABLE
    else:
        update_status = ImageUpdateStatus.UPDATE_AVAILABLE

    return BootSourceSelectionStatus(
        id=selection.id,
        status=status,
        update_status=update_status,
        sync_percentage=sync_size * 100 / file_size,
        selected=True,
    )

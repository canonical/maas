# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
import json

from maasservicelayer.db.tables import ImageManifestTable
from maasservicelayer.models.image_manifests import ImageManifest
from maasservicelayer.utils.date import utcnow
from tests.fixtures import get_test_data_file
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_image_manifest_entry(
    fixture: Fixture,
    boot_source_id: int,
    last_update: datetime | None = None,
    **extra,
) -> ImageManifest:
    if last_update is None:
        last_update = utcnow()
    manifest = get_test_data_file("simplestreams_ubuntu.json")
    manifest = json.loads(manifest)
    image_manifest = {
        "boot_source_id": boot_source_id,
        "manifest": [manifest],
        "last_update": last_update,
    }

    image_manifest.update(extra)

    [created_image_manifest] = await fixture.create(
        ImageManifestTable.name, [image_manifest]
    )

    return ImageManifest(**created_image_manifest)

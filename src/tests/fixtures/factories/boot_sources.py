# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasservicelayer.db.tables import BootSourceTable
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping
from maasservicelayer.utils.images.helpers import ImageSpec
from maastesting.factory import factory
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_bootsource_entry(
    fixture: Fixture, url, priority, **extra_details
) -> BootSource:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()

    bootsource = {
        "created": created_at,
        "updated": updated_at,
        "url": url,
        "keyring_filename": "/path/to/keyring.gpg",
        "keyring_data": b"data",
        "priority": priority,
        "skip_keyring_verification": False,
    }
    bootsource.update(extra_details)

    [created_bootsource] = await fixture.create(
        BootSourceTable.name, bootsource
    )

    return BootSource(**created_bootsource)


def make_image_spec(
    os: str | None = None,
    arch: str | None = None,
    subarch: str | None = None,
    release: str | None = None,
    kflavor: str | None = None,
    label: str | None = None,
) -> ImageSpec:
    """
    Build an `ImageSpec` with random values.
    """
    if os is None:
        os = factory.make_name("os")
    if arch is None:
        arch = factory.make_name("arch")
    if subarch is None:
        subarch = factory.make_name("subarch")
    if kflavor is None:
        kflavor = "generic"
    if release is None:
        release = factory.make_name("release")
    if label is None:
        label = factory.make_name("label")
    return ImageSpec(os, arch, subarch, kflavor, release, label)


def set_resource(
    boot_dict: BootImageMapping | None = None,
    image_spec: ImageSpec | None = None,
    resource=None,
) -> BootImageMapping:
    """
    Add boot resource to a `BootImageMapping`, creating it if necessary.
    """
    if boot_dict is None:
        boot_dict = BootImageMapping()
    if image_spec is None:
        image_spec = make_image_spec()
    if resource is None:
        resource = factory.make_name("boot-resource")
    boot_dict.mapping[image_spec] = resource
    return boot_dict

# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Factory helpers for the `import_images` package."""

from maasserver.import_images.boot_image_mapping import BootImageMapping
from maasserver.import_images.helpers import ImageSpec
from maastesting.factory import factory


def make_boot_resource():
    """Create a fake resource dict."""
    return {
        "content_id": factory.make_name("content_id"),
        "product_name": factory.make_name("product_name"),
        "version_name": factory.make_name("version_name"),
    }


def make_image_spec(
    os=None, arch=None, subarch=None, release=None, kflavor=None, label=None
):
    """Return an `ImageSpec` with random values."""
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


def set_resource(boot_dict=None, image_spec=None, resource=None):
    """Add boot resource to a `BootImageMapping`, creating it if necessary."""
    if boot_dict is None:
        boot_dict = BootImageMapping()
    if image_spec is None:
        image_spec = make_image_spec()
    if resource is None:
        resource = factory.make_name("boot-resource")
    boot_dict.mapping[image_spec] = resource
    return boot_dict

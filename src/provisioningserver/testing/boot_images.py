# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test helpers for boot-image parameters."""
from typing import Dict

from maastesting.factory import factory


def make_boot_image_params():
    """Create an arbitrary dict of boot-image parameters.

    These are the parameters that together describe a kind of boot for
    which we may need a kernel and initrd: operating system, architecture,
    sub-architecture, Ubuntu release, boot purpose, and release label.
    """
    return dict(
        osystem=factory.make_name("osystem"),
        architecture=factory.make_name("architecture"),
        subarchitecture=factory.make_name("subarchitecture"),
        release=factory.make_name("release"),
        label=factory.make_name("label"),
        purpose=factory.make_name("purpose"),
        platform=factory.make_name("platform"),
        supported_subarches=factory.make_name("sup_subarches"),
    )


def make_boot_image_storage_params():
    """Create a dict of boot-image parameters as used to store the image.

    These are the parameters that together describe a path to store a boot
    image: operating system, architecture, sub-architecture, Ubuntu release,
    and release label.
    """
    return dict(
        osystem=factory.make_name("osystem"),
        architecture=factory.make_name("architecture"),
        subarchitecture=factory.make_name("subarchitecture"),
        release=factory.make_name("release"),
        label=factory.make_name("label"),
    )


def make_image(
    params, purpose, metadata=None, xinstall_path=None, xinstall_type=None
) -> Dict:
    """Describe an image as a dict similar to what `list_boot_images` returns.

    The `params` are as returned from `make_boot_image_storage_params`.
    """
    image = params.copy()
    image["purpose"] = purpose
    if metadata is not None:
        image.update(metadata)
    if purpose == "xinstall":
        if xinstall_path is None:
            xinstall_path = "root-tgz"
        if xinstall_type is None:
            xinstall_type = "tgz"
        image["xinstall_path"] = xinstall_path
        image["xinstall_type"] = xinstall_type
    else:
        image["xinstall_path"] = ""
        image["xinstall_type"] = ""
    return image

# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The `BootImageMapping` class."""

from maasserver.import_images.helpers import ImageSpec


def gen_image_spec_with_resource(os, data):
    """Generate image and resource for given operating system and data."""
    for arch in data:
        for subarch in data[arch]:
            for kflavor in data[arch][subarch]:
                for release in data[arch][subarch][kflavor]:
                    for label in data[arch][subarch][kflavor][release]:
                        image = ImageSpec(
                            os=os,
                            arch=arch,
                            subarch=subarch,
                            kflavor=kflavor,
                            release=release,
                            label=label,
                        )
                        resource = data[arch][subarch][kflavor][release][label]
                        yield image, resource


def gen_image_spec_with_resource_legacy(os, data):
    """Generate image and resource for given operating system and data.

    Prior to 2.1 we didn't store the kflavor. This reads the old format so
    users aren't forced to reimport all images on upgrade. 'generic' is used
    as the kflavor as prior to 2.1 MAAS only supported generic kernels."""
    for arch in data:
        for subarch in data[arch]:
            for release in data[arch][subarch]:
                for label in data[arch][subarch][release]:
                    image = ImageSpec(
                        os=os,
                        arch=arch,
                        subarch=subarch,
                        kflavor="generic",
                        release=release,
                        label=label,
                    )
                    resource = data[arch][subarch][release][label]
                    yield image, resource


class BootImageMapping:
    """Mapping of boot-image data.

    Maps `ImageSpec` tuples to metadata for Simplestreams products.

    This class is deliberately a bit more restrictive and less ad-hoc than a
    dict.  It helps keep a clear view of the data structures in this module.
    """

    def __init__(self):
        self.mapping = {}

    def items(self):
        """Iterate over `ImageSpec` keys, and their stored values."""
        yield from sorted(self.mapping.items())

    def is_empty(self):
        """Is this mapping empty?"""
        return len(self.mapping) == 0

    def setdefault(self, image_spec, item):
        """Set metadata for `image_spec` to item, if not already set."""
        assert isinstance(image_spec, ImageSpec)
        self.mapping.setdefault(image_spec, item)

    def set(self, image_spec, item):
        """ "Set metadata for `image_spec` to item, even if already set."""
        assert isinstance(image_spec, ImageSpec)
        self.mapping[image_spec] = item

    def get_image_arches(self):
        """Set of arches this BootImageMapping has an ImageSpec for."""
        return {item[0].arch for item in self.items()}

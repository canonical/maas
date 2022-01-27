# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The `BootImageMapping` class."""


import json

from provisioningserver.import_images.helpers import ImageSpec
from provisioningserver.utils import dict_depth


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
        """"Set metadata for `image_spec` to item, even if already set."""
        assert isinstance(image_spec, ImageSpec)
        self.mapping[image_spec] = item

    def dump_json(self):
        """Produce JSON representing the mapped boot images.

        Tries to keep the output deterministic, so that identical data is
        likely to produce identical JSON.

        :return: A Unicode string (`str`) containing JSON using only ASCII
            characters.
        """
        # The meta files represent the mapping as a nested hierarchy of dicts.
        # Keep that format.
        data = {}
        for image, resource in self.items():
            os, arch, subarch, kflavor, release, label = image
            data.setdefault(os, {})
            data[os].setdefault(arch, {})
            data[os][arch].setdefault(subarch, {})
            data[os][arch][subarch].setdefault(kflavor, {})
            data[os][arch][subarch][kflavor].setdefault(release, {})
            data[os][arch][subarch][kflavor][release][label] = resource
        return json.dumps(data, sort_keys=True)

    @staticmethod
    def load_json(json_data):
        """Take a JSON representation and deserialize into an object.

        :param json_data: string produced by dump_json(), above.
        :return: A BootImageMapping

        If the json data is invalid, an empty BootImageMapping is returned.
        """
        mapping = BootImageMapping()
        try:
            data = json.loads(json_data)
        except ValueError:
            return mapping

        depth = dict_depth(data)
        if depth == 5:
            # Support for older data. This has no operating system, then
            # it is ubuntu.
            for image, resource in gen_image_spec_with_resource(
                "ubuntu", data
            ):
                mapping.setdefault(image, resource)
        elif depth == 6:
            for os in data:
                for image, resource in gen_image_spec_with_resource_legacy(
                    os, data[os]
                ):
                    mapping.setdefault(image, resource)
        elif depth == 7:
            for os in data:
                for image, resource in gen_image_spec_with_resource(
                    os, data[os]
                ):
                    mapping.setdefault(image, resource)
        return mapping

    def get_image_arches(self):
        """Set of arches this BootImageMapping has an ImageSpec for."""
        return {item[0].arch for item in self.items()}

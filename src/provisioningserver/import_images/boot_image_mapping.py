# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The `BootImageMapping` class."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootImageMapping',
    ]

import json

from provisioningserver.import_images.helpers import ImageSpec


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
        for image_spec, item in sorted(self.mapping.items()):
            yield image_spec, item

    def setdefault(self, image_spec, item):
        """Set metadata for `image_spec` to item, if not already set."""
        assert isinstance(image_spec, ImageSpec)
        self.mapping.setdefault(image_spec, item)

    def dump_json(self):
        """Produce JSON representing the mapped boot images.

        Tries to keep the output deterministic, so that identical data is
        likely to produce identical JSON.
        """
        # The meta files represent the mapping as a nested hierarchy of dicts.
        # Keep that format.
        data = {}
        for image, resource in self.items():
            arch, subarch, release, label = image
            data.setdefault(arch, {})
            data[arch].setdefault(subarch, {})
            data[arch][subarch].setdefault(release, {})
            data[arch][subarch][release][label] = resource
        return json.dumps(data, sort_keys=True)

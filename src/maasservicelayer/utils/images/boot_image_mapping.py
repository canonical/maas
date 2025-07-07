# Copyright 2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, Iterator, Set

from maasservicelayer.utils.images.helpers import ImageSpec


class BootImageMapping:
    """Mapping of boot-image data.

    Maps `ImageSpec` tuples to metadata for Simplestreams products.

    This class is deliberately a bit more restrictive and less ad-hoc than a
    dict.  It helps keep a clear view of the data structures in this module.
    """

    def __init__(self) -> None:
        self.mapping = {}

    def items(self) -> Iterator[tuple[ImageSpec, Any]]:
        """Iterate over `ImageSpec` keys, and their stored values."""
        yield from sorted(self.mapping.items())

    def __len__(self) -> int:
        """Return the number of items in this mapping."""
        return len(self.mapping)

    def is_empty(self) -> bool:
        """Is this mapping empty?"""
        return len(self.mapping) == 0

    def setdefault(self, image_spec: ImageSpec, item: Any) -> None:
        """Set metadata for `image_spec` to item, if not already set."""
        assert isinstance(image_spec, ImageSpec)
        self.mapping.setdefault(image_spec, item)

    def set(self, image_spec: ImageSpec, item: Any) -> None:
        """ "Set metadata for `image_spec` to item, even if already set."""
        assert isinstance(image_spec, ImageSpec)
        self.mapping[image_spec] = item

    def get_image_arches(self) -> Set[str]:
        """Set of arches this BootImageMapping has an ImageSpec for."""
        return {item[0].arch for item in self.items()}

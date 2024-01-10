# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The `ProductMapping` class."""


class ProductMapping:
    """Mapping of product data.

    Maps a combination of boot resource metadata (`content_id`, `product_name`,
    `version_name`) to a list of subarchitectures supported by that boot
    resource.
    """

    def __init__(self):
        self.mapping = {}

    @staticmethod
    def make_key(resource):
        """Extract a key tuple from `resource`.

        The key is used for indexing `mapping`.

        :param resource: A dict describing a boot resource.  It must contain
            the keys `content_id`, `product_name`, and `version_name`.
        :return: A tuple of the resource's content ID, product name, and
            version name.
        """
        return (
            resource["content_id"],
            resource["product_name"],
            resource["version_name"],
        )

    def add(self, resource, subarch):
        """Add `subarch` to the list of subarches supported by a boot resource.

        The `resource` is a dict as returned by `products_exdata`.  The method
        will use the values identified by keys `content_id`, `product_name`,
        and `version_name`.
        """
        key = self.make_key(resource)
        self.mapping.setdefault(key, [])
        self.mapping[key].append(subarch)

    def contains(self, resource):
        """Does the dict contain a mapping for the given resource?"""
        return self.make_key(resource) in self.mapping

    def get(self, resource):
        """Return the mapped subarchitectures for `resource`."""
        return self.mapping[self.make_key(resource)]


def map_products(image_descriptions):
    """Determine the subarches supported by each boot resource.

    Many subarches may be deployed by a single boot resource.  We note only
    subarchitectures here and ignore architectures because the metadata format
    tightly couples a boot resource to its architecture.

    We can figure out for which architecture we need to use a specific boot
    resource by looking at its description in the metadata.  We can't do the
    same with subarch, because we may want to use a boot resource only for a
    specific subset of subarches.

    This function returns the relationship between boot resources and
    subarchitectures as a `ProductMapping`.

    :param image_descriptions: A `BootImageMapping` containing the images'
        metadata.
    :return: A `ProductMapping` mapping products to subarchitectures.
    """
    mapping = ProductMapping()
    for image, boot_resource in image_descriptions.items():
        mapping.add(boot_resource, image.subarch)
    return mapping

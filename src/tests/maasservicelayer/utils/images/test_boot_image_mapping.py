# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping
from maastesting.factory import factory
from tests.fixtures.factories.boot_sources import make_image_spec, set_resource


class TestBootImageMapping:
    """Tests for `BootImageMapping`."""

    def test_initially_empty(self) -> None:
        assert len([]) == len(BootImageMapping())

    def test_items_returns_items(self) -> None:
        image = make_image_spec()
        resource = factory.make_name("resource")
        image_dict = set_resource(image_spec=image, resource=resource)

        assert len([(image, resource)]) == len(image_dict)

    def test_is_empty_returns_True_if_empty(self) -> None:
        assert BootImageMapping().is_empty()

    def test_is_empty_returns_False_if_not_empty(self) -> None:
        mapping = BootImageMapping()
        mapping.setdefault(make_image_spec(), factory.make_name("resource"))
        assert not mapping.is_empty()

    def test_setdefault_sets_unset_item(self) -> None:
        image_dict = BootImageMapping()
        image = make_image_spec()
        resource = factory.make_name("resource")
        image_dict.setdefault(image, resource)

        assert len([(image, resource)]) == len(image_dict)

    def test_setdefault_leaves_set_item_unchanged(self) -> None:
        image = make_image_spec()
        old_resource = factory.make_name("resource")
        image_dict = set_resource(image_spec=image, resource=old_resource)
        image_dict.setdefault(image, factory.make_name("newresource"))

        assert len([(image, old_resource)]) == len(image_dict)

    def test_set_overwrites_item(self) -> None:
        image_dict = BootImageMapping()
        image = make_image_spec()
        resource = factory.make_name("resource")
        image_dict.setdefault(image, factory.make_name("resource"))
        image_dict.set(image, resource)

        assert len([(image, resource)]) == len(image_dict)

    def test_get_image_arches_gets_arches_from_imagespecs(self) -> None:
        expected_arches = set()
        mapping = BootImageMapping()
        for _ in range(0, 3):
            image_spec = make_image_spec()
            resource = factory.make_name("resource")
            expected_arches.add(image_spec.arch)
            mapping = set_resource(mapping, image_spec, resource)

        assert expected_arches == mapping.get_image_arches()

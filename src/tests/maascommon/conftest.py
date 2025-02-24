#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
import pytest

from maascommon.osystem import (
    BOOT_IMAGE_PURPOSE,
    OperatingSystem,
    OperatingSystemRegistry,
)
from maascommon.utils.registry import _registry
from maastesting.factory import factory


class FakeOS(OperatingSystem):
    name = ""
    title = ""

    def __init__(self, name, purpose=None, releases=None):
        self.name = name
        self.title = name
        self.purpose = purpose
        if releases is None:
            self.fake_list = [factory.make_string() for _ in range(3)]
        else:
            self.fake_list = releases

    def get_boot_image_purposes(self, *args):
        if self.purpose is None:
            return [BOOT_IMAGE_PURPOSE.XINSTALL]
        else:
            return self.purpose

    def get_supported_releases(self):
        return self.fake_list

    def get_default_release(self):
        return self.fake_list[0]

    def get_release_title(self, release):
        return release


@pytest.fixture
def temporary_os():
    osystem = factory.make_name("os")
    purpose = [
        BOOT_IMAGE_PURPOSE.COMMISSIONING,
        BOOT_IMAGE_PURPOSE.INSTALL,
        BOOT_IMAGE_PURPOSE.XINSTALL,
    ]
    fake = FakeOS(osystem, purpose)
    OperatingSystemRegistry.register_item(fake.name, fake)
    yield fake
    OperatingSystemRegistry.unregister_item(osystem)


@pytest.fixture
def osystem_registry():
    registry_copy = _registry.copy()
    _registry.clear()
    yield
    _registry.clear()
    _registry.update(registry_copy)

import pytest

from maascommon.osystem.ol import BOOT_IMAGE_PURPOSE, DISTRO_SERIES_DEFAULT, OL


@pytest.fixture
def ol():
    return OL()


def test_get_boot_image_purposes(ol):
    assert ol.get_boot_image_purposes() == [BOOT_IMAGE_PURPOSE.XINSTALL]


def test_get_default_release(ol):
    assert ol.get_default_release() == DISTRO_SERIES_DEFAULT


@pytest.mark.parametrize(
    "release,title",
    [
        ("ol8", "Oracle Linux 8"),
        ("ol9.2", "Oracle Linux 9.2"),
        ("ol9.2-custom", "Oracle Linux 9.2 custom"),
        ("nol", "Oracle Linux nol"),
    ],
)
def test_get_release_title(ol, release, title):
    assert ol.get_release_title(release) == title

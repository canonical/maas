#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.utils.date import utcnow


def make_boot_resource(
    architecture: str, extra: dict, name: str = "ubuntu/noble"
) -> BootResource:
    return BootResource(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        rtype=BootResourceType.SYNCED,
        name=name,
        architecture=architecture,
        extra=extra,
        rolling=False,
        base_image="",
    )


class TestBootResource:
    @pytest.mark.parametrize(
        "architecture, extra, subarch, expected",
        [
            ("amd64/generic", {}, "generic", True),
            ("amd64/generic", {}, "hwe-22.04", False),
            (
                "amd64/generic",
                {"subarches": "generic,hwe-22.04"},
                "hwe-22.04",
                True,
            ),
            ("amd64/generic", {"subarches": "hwe-22.04"}, "generic", True),
            ("amd64/generic", {"subarches": "hwe-22.04"}, "hwe-24.04", False),
        ],
    )
    def test_supports_subarch(
        self, architecture: str, extra: dict, subarch: str, expected: bool
    ):
        resource = make_boot_resource(architecture, extra)
        assert resource.supports_subarch(subarch) is expected

    @pytest.mark.parametrize(
        "architecture, extra, platform, expected",
        [
            ("amd64/generic", {}, "generic", True),
            ("amd64/generic", {}, "xgene-uboot", False),
            (
                "arm64/generic",
                {"platform": "xgene-uboot"},
                "xgene-uboot",
                True,
            ),
            ("arm64/generic", {"platform": "xgene-uboot"}, "rpi4", False),
            (
                "arm64/generic",
                {"supported_platforms": "rpi4,rpi5"},
                "rpi5",
                True,
            ),
            (
                "arm64/generic",
                {"platform": "xgene-uboot", "supported_platforms": "rpi4"},
                "rpi4",
                True,
            ),
            (
                "arm64/generic",
                {"subarches": "hwe-22.04"},
                "hwe-22.04",
                False,
            ),
        ],
    )
    def test_supports_platform(
        self, architecture: str, extra: dict, platform: str, expected: bool
    ):
        resource = make_boot_resource(architecture, extra)
        assert resource.supports_platform(platform) is expected

    @pytest.mark.parametrize(
        "architecture, expected",
        [
            ("amd64/generic", ("amd64", "generic")),
            ("arm64/hwe-22.04", ("arm64", "hwe-22.04")),
            ("amd64/ga-24.04/lowlatency", ("amd64", "ga-24.04/lowlatency")),
        ],
    )
    def test_split_arch(self, architecture: str, expected: tuple[str, str]):
        resource = make_boot_resource(architecture, {})
        assert resource.split_arch() == expected

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("ubuntu/noble", ("ubuntu", "noble")),
            ("centos/8", ("centos", "8")),
            ("my-custom-image", ("custom", "my-custom-image")),
            ("ubuntu/noble/extra", ("ubuntu", "noble/extra")),
        ],
    )
    def test_split_name(self, name: str, expected: tuple[str, str]):
        resource = make_boot_resource("amd64/generic", {}, name=name)
        assert resource.split_name() == expected

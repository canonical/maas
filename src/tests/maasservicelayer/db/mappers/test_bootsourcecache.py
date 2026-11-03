# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from types import MappingProxyType

from maasservicelayer.db.mappers.bootsourcecache import (
    BootSourceAvailableImageDataMapper,
    BootSourceCacheOSReleaseDataMapper,
)
from maasservicelayer.models.bootsources import (
    BootSourceAvailableImage,
    BootSourceCacheOSRelease,
)


class TestBootSourceAvailableImageDataMapper:
    def test_to_domain_preserves_image_values(self):
        row = MappingProxyType(
            {
                "os": "ubuntu",
                "release": "noble",
                "release_title": "24.04 LTS",
                "arch": "arm64",
                "boot_source_id": 7,
            }
        )

        image = BootSourceAvailableImageDataMapper().to_domain(row)

        assert image == BootSourceAvailableImage(
            "ubuntu", "noble", "24.04 LTS", "arm64", 7
        )
        assert row["boot_source_id"] == 7

    def test_known_boot_source_does_not_mutate_projection(self):
        values = {
            "os": "centos",
            "release": "8",
            "release_title": "CentOS 8",
            "arch": "amd64",
        }
        row = MappingProxyType(values.copy())

        image = BootSourceAvailableImageDataMapper().to_domain_for_boot_source(
            row, 9
        )

        assert image == BootSourceAvailableImage(
            "centos", "8", "CentOS 8", "amd64", 9
        )
        assert row == values


class TestBootSourceCacheOSReleaseDataMapper:
    def test_to_domain_preserves_named_projection_values(self):
        row = MappingProxyType({"release": "mellanox-3.8.0", "os": "onie"})

        release = BootSourceCacheOSReleaseDataMapper().to_domain(row)

        assert release == BootSourceCacheOSRelease("onie", "mellanox-3.8.0")
        assert row == {"release": "mellanox-3.8.0", "os": "onie"}

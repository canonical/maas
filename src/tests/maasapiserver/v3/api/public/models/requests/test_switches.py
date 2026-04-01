#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasapiserver.v3.api.public.models.requests.switches import (
    resolve_image_id,
)
from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.bootresources import BootResourceService


def _boot_resource(id: int, name: str) -> BootResource:
    return BootResource(
        id=id,
        rtype=BootResourceType.UPLOADED,
        name=name,
        architecture="amd64/generic",
        extra={},
        rolling=False,
        base_image="",
    )


@pytest.mark.asyncio
class TestResolveImageId:
    async def test_returns_none_when_image_is_none(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)

        image_id = await resolve_image_id(None, services_mock)

        assert image_id is None
        services_mock.boot_resources.get_one.assert_not_called()

    async def test_returns_boot_resource_id_for_full_onie_name(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = _boot_resource(
            10, "onie/mellanox-3.8.0"
        )

        image_id = await resolve_image_id("onie/mellanox-3.8.0", services_mock)

        assert image_id == 10
        services_mock.boot_resources.get_one.assert_called_once()

    async def test_raises_when_full_name_resolves_to_non_onie_image(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = _boot_resource(
            11, "ubuntu/noble"
        )

        with pytest.raises(ValidationException) as exc:
            await resolve_image_id("ubuntu/noble", services_mock)
            assert exc.value.details[0].field == "image"
            assert exc.value.details[0].message == (
                "Image 'ubuntu/noble' was found but is not an ONIE image. "
                "Found: 'ubuntu/noble'."
            )
        services_mock.boot_resources.get_one.assert_called_once()

    async def test_resolves_short_name_with_onie_prefix_fallback(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.side_effect = [
            None,
            _boot_resource(12, "onie/dellos10"),
        ]

        image_id = await resolve_image_id("dellos10", services_mock)

        assert image_id == 12
        assert services_mock.boot_resources.get_one.call_count == 2

    async def test_raises_when_short_name_not_found(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.side_effect = [None, None]

        with pytest.raises(ValidationException) as exc:
            await resolve_image_id("missing-image", services_mock)

            assert exc.value.details[0].field == "image"
            assert exc.value.details[0].message == (
                "Boot resource 'missing-image' not found. "
                "Use full format 'onie/vendor-version' or short format "
                "'vendor-version' for ONIE images. "
                "Use 'boot_resources' endpoint to list available images."
            )
        assert services_mock.boot_resources.get_one.call_count == 2

    async def test_raises_when_full_name_not_found(
        self, services_mock: ServiceCollectionV3
    ) -> None:
        services_mock.boot_resources = Mock(BootResourceService)
        services_mock.boot_resources.get_one.return_value = None

        with pytest.raises(ValidationException) as exc:
            await resolve_image_id("onie/missing-image", services_mock)

            assert exc.value.details[0].field == "image"
            assert exc.value.details[0].message == (
                "Boot resource 'onie/missing-image' not found. "
                "Use full format 'onie/vendor-version' or short format "
                "'vendor-version' for ONIE images. "
                "Use 'boot_resources' endpoint to list available images."
            )
        services_mock.boot_resources.get_one.assert_called_once()

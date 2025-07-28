# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.boot_resources import BootResourceType
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
    BootResourcesRepository,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.simplestreams.models import BootloaderProduct
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_BOOT_RESOURCE = BootResource(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    rtype=BootResourceType.SYNCED,
    name="ubuntu/noble",
    architecture="amd64/generic",
    rolling=False,
    base_image="",
    extra={},
)


class TestCommonBootResourceService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BootResourceService:
        return BootResourceService(
            context=Context(),
            repository=Mock(BootResourcesRepository),
            boot_resource_sets_service=Mock(BootResourceSetsService),
        )

    @pytest.fixture
    def test_instance(self) -> BootResource:
        return TEST_BOOT_RESOURCE


class TestBootResourceService:
    @pytest.fixture
    def mock_repository(self) -> Mock:
        return Mock(BootResourcesRepository)

    @pytest.fixture
    def mock_boot_resource_sets_service(self) -> Mock:
        return Mock(BootResourceSetsService)

    @pytest.fixture
    def service(
        self, mock_repository: Mock, mock_boot_resource_sets_service: Mock
    ) -> BootResourceService:
        return BootResourceService(
            context=Context(),
            repository=mock_repository,
            boot_resource_sets_service=mock_boot_resource_sets_service,
        )

    async def test_pre_delete_hook(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_by_id.return_value = TEST_BOOT_RESOURCE
        await service.delete_by_id(TEST_BOOT_RESOURCE.id)
        mock_boot_resource_sets_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_id(
                    TEST_BOOT_RESOURCE.id
                )
            )
        )

    async def test_pre_delete_many_hook(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_many.return_value = [TEST_BOOT_RESOURCE]
        await service.delete_many(query=QuerySpec())
        mock_boot_resource_sets_service.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_ids(
                    [TEST_BOOT_RESOURCE.id]
                )
            )
        )

    async def test_delete_all_without_sets(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_boot_resource_sets_service.get_many.return_value = [
            BootResourceSet(
                id=1,
                created=utcnow(),
                updated=utcnow(),
                version="20250618",
                label="stable",
                resource_id=TEST_BOOT_RESOURCE.id,
            ),
        ]

        await service.delete_all_without_sets()

        mock_repository.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.not_clause(
                    BootResourceClauseFactory.with_ids({TEST_BOOT_RESOURCE.id})
                )
            )
        )

    async def test_delete_all_without_sets_delete_all_boot_resources(
        self,
        mock_repository: Mock,
        mock_boot_resource_sets_service: Mock,
        service: BootResourceService,
    ) -> None:
        mock_boot_resource_sets_service.get_many.return_value = []

        await service.delete_all_without_sets()

        mock_repository.delete_many.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.not_clause(
                    BootResourceClauseFactory.with_ids(set())
                )
            )
        )

    async def test_create_or_update_from_simplestreams_product__create(
        self,
        mock_repository: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_one.return_value = None
        mock_repository.create.return_value = TEST_BOOT_RESOURCE

        # we have to do it this way because of fields with hyphens
        product = BootloaderProduct(
            **{
                "product_name": "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
                "arch": "amd64",
                "arches": "amd64",
                "bootloader-type": "uefi",
                "label": "stable",
                "os": "grub-efi-signed",
                "versions": [],
            }
        )
        builder = BootResourceBuilder.from_simplestreams_product(product)
        await service.create_or_update_from_simplestreams_product(product)

        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            builder.ensure_set(builder.rtype)
                        ),
                        BootResourceClauseFactory.with_name(
                            builder.ensure_set(builder.name)
                        ),
                        BootResourceClauseFactory.with_architecture(
                            builder.ensure_set(builder.architecture)
                        ),
                        BootResourceClauseFactory.with_alias(
                            builder.ensure_set(builder.alias)
                        ),
                    ]
                )
            ),
        )

        mock_repository.create.assert_awaited_once_with(builder=builder)

    async def test_create_or_update_from_simplestreams_product__update(
        self,
        mock_repository: Mock,
        service: BootResourceService,
    ) -> None:
        mock_repository.get_one.return_value = TEST_BOOT_RESOURCE
        mock_repository.update_by_id.return_value = TEST_BOOT_RESOURCE

        # we have to do it this way because of fields with hyphens
        product = BootloaderProduct(
            **{
                "product_name": "com.ubuntu.maas.stable:1:grub-efi-signed:uefi:amd64",
                "arch": "amd64",
                "arches": "amd64",
                "bootloader-type": "uefi",
                "label": "stable",
                "os": "grub-efi-signed",
                "versions": [],
            }
        )
        builder = BootResourceBuilder.from_simplestreams_product(product)
        await service.create_or_update_from_simplestreams_product(product)

        mock_repository.get_one.assert_awaited_once_with(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_rtype(
                            builder.ensure_set(builder.rtype)
                        ),
                        BootResourceClauseFactory.with_name(
                            builder.ensure_set(builder.name)
                        ),
                        BootResourceClauseFactory.with_architecture(
                            builder.ensure_set(builder.architecture)
                        ),
                        BootResourceClauseFactory.with_alias(
                            builder.ensure_set(builder.alias)
                        ),
                    ]
                )
            ),
        )

        mock_repository.update_by_id.assert_awaited_once_with(
            id=TEST_BOOT_RESOURCE.id, builder=builder
        )
        mock_repository.create.assert_not_awaited()

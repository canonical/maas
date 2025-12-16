# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageResponse,
    ImageStatisticResponse,
    ImageStatusResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BootResourceType,
    ImageStatus,
    ImageUpdateStatus,
)
from maascommon.utils.converters import human_readable_bytes
from maasservicelayer.models.bootresources import (
    BootResource,
    CustomBootResourceStatistic,
    CustomBootResourceStatus,
)
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatistic,
    BootSourceSelectionStatus,
)
from maasservicelayer.utils.date import utcnow


class TestImageResponse:
    def test_from_model__selection(self) -> None:
        selection = BootSourceSelection(
            id=1,
            os="ubuntu",
            release="noble",
            arch="amd64",
            boot_source_id=1,
            legacyselection_id=1,
        )
        response = ImageResponse.from_selection(
            selection, self_base_hyperlink=f"{V3_API_PREFIX}/selections"
        )
        assert response.id == selection.id
        assert response.os == selection.os
        assert response.release == selection.release
        assert response.title == "24.04 LTS"
        assert response.architecture == selection.arch
        assert response.boot_source_id == selection.boot_source_id
        assert response.hal_links.self.href == f"{V3_API_PREFIX}/selections/1"

    def test_from_model__boot_resource(self) -> None:
        boot_resource = BootResource(
            id=1,
            name="custom-ubuntu/noble",
            architecture="amd64/generic",
            rtype=BootResourceType.UPLOADED,
            extra={},
            rolling=False,
            base_image="",
        )
        response = ImageResponse.from_boot_resource(
            boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_resources",
        )
        assert response.id == boot_resource.id
        assert response.os == "custom-ubuntu"
        assert response.release == "noble"
        assert response.title == "24.04 LTS"
        assert response.architecture == "amd64"
        assert response.boot_source_id is None
        assert (
            response.hal_links.self.href == f"{V3_API_PREFIX}/boot_resources/1"
        )


class TestImageStatusResponse:
    def test_from_model__selection(self) -> None:
        status = BootSourceSelectionStatus(
            id=1,
            status=ImageStatus.READY,
            update_status=ImageUpdateStatus.NO_UPDATES_AVAILABLE,
            sync_percentage=100.0,
            selected=True,
        )

        response = ImageStatusResponse.from_model(status=status)
        assert response.id == status.id
        assert response.status == status.status
        assert response.update_status == status.update_status
        assert response.sync_percentage == status.sync_percentage
        assert response.selected == status.selected

    def test_from_model__custom_image(self) -> None:
        status = CustomBootResourceStatus(
            id=1,
            status=ImageStatus.READY,
            sync_percentage=100.0,
        )
        response = ImageStatusResponse.from_model(status=status)
        assert response.id == status.id
        assert response.status == status.status
        assert response.update_status == status.update_status
        assert response.sync_percentage == status.sync_percentage
        assert response.selected == status.selected


class TestImageStatisticResponse:
    def test_from_model__selection(self) -> None:
        stat = BootSourceSelectionStatistic(
            id=1,
            last_updated=utcnow(),
            last_deployed=None,
            size=1024,
            node_count=1,
            deploy_to_memory=True,
        )
        response = ImageStatisticResponse.from_model(stat)
        assert response.id == stat.id
        assert response.last_updated == stat.last_updated
        assert response.last_deployed == stat.last_deployed
        assert response.size == human_readable_bytes(stat.size)
        assert response.node_count == stat.node_count
        assert response.deploy_to_memory == stat.deploy_to_memory

    def test_from_model__custom_image(self) -> None:
        stat = CustomBootResourceStatistic(
            id=1,
            last_updated=utcnow(),
            last_deployed=None,
            size=1024,
            node_count=1,
            deploy_to_memory=True,
        )
        response = ImageStatisticResponse.from_model(stat)
        assert response.id == stat.id
        assert response.last_updated == stat.last_updated
        assert response.last_deployed == stat.last_deployed
        assert response.size == human_readable_bytes(stat.size)
        assert response.node_count == stat.node_count
        assert response.deploy_to_memory == stat.deploy_to_memory

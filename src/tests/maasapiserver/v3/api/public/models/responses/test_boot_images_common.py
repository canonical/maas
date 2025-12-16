# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageStatisticResponse,
    ImageStatusResponse,
)
from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maascommon.utils.converters import human_readable_bytes
from maasservicelayer.models.bootresources import (
    CustomBootResourceStatistic,
    CustomBootResourceStatus,
)
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelectionStatistic,
    BootSourceSelectionStatus,
)
from maasservicelayer.utils.date import utcnow


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

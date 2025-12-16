# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageStatusResponse,
)
from maascommon.enums.boot_resources import ImageStatus, ImageUpdateStatus
from maasservicelayer.models.bootresources import CustomBootResourceStatus
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelectionStatus,
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

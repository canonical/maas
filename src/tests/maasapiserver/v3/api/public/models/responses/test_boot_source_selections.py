# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.boot_source_selections import (
    BootSourceSelectionResponse,
    BootSourceSelectionStatusResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.bootsourceselections import (
    BootSourceSelection,
    BootSourceSelectionStatus,
    SelectionStatus,
    SelectionUpdateStatus,
)


class TestBootSourceSelectionResponse:
    def test_from_model(self) -> None:
        selection = BootSourceSelection(
            id=1,
            os="ubuntu",
            release="focal",
            arch="amd64",
            boot_source_id=42,
        )
        response = BootSourceSelectionResponse.from_model(
            boot_source_selection=selection,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources/1/selections",
        )
        assert response.id == selection.id
        assert response.os == selection.os
        assert response.release == selection.release
        assert response.arch == selection.arch
        assert response.boot_source_id == selection.boot_source_id
        assert (
            response.hal_links.self.href
            == f"{V3_API_PREFIX}/boot_sources/1/selections/1"
        )


class TestBootSourceSelectionStatusResponse:
    def test_from_model(self) -> None:
        status = BootSourceSelectionStatus(
            id=1,
            status=SelectionStatus.READY,
            update_status=SelectionUpdateStatus.NO_UPDATES_AVAILABLE,
            sync_percentage=100.0,
            selected=True,
        )

        response = BootSourceSelectionStatusResponse.from_model(status=status)
        assert response.selection_id == status.id
        assert response.status == status.status
        assert response.update_status == status.update_status
        assert response.sync_percentage == status.sync_percentage
        assert response.selected == status.selected

# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.boot_source_selections import (
    BootSourceSelectionResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.bootsourceselections import BootSourceSelection


class TestBootSourceSelectionResponse:
    def test_from_model(self) -> None:
        selection = BootSourceSelection(
            id=1,
            os="ubuntu",
            release="focal",
            arch="amd64",
            boot_source_id=42,
            legacyselection_id=1,
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

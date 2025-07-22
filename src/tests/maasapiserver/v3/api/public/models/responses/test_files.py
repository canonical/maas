#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from maasapiserver.v3.api.public.models.responses.files import (
    FileListItemResponse,
    FileResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.filestorage import FileStorage


class TestFileResponse:
    def test_from_model(self) -> None:
        file = FileStorage(
            id=1,
            filename="abc.sh",
            content=b"echo Hello world",
            key="abc",
            owner_id=0,
        )

        response = FileResponse.from_model(
            file=file, self_base_hyperlink=f"{V3_API_PREFIX}/files"
        )

        assert file.id == response.id
        assert file.filename == response.filename
        assert file.key == response.key
        assert file.owner_id == response.owner_id
        assert (
            response.hal_links.self.href == f"{V3_API_PREFIX}/files/{file.id}"
        )

        # Make sure file content got base64-encoded so we can serialise it to JSON
        assert response.content == "ZWNobyBIZWxsbyB3b3JsZA=="


class TestFileListItemResponse:
    def test_from_model(self) -> None:
        file = FileStorage(
            id=1,
            filename="abc.sh",
            content=b"echo Hello world",
            key="abc",
            owner_id=0,
        )

        response = FileListItemResponse.from_model(
            file=file, self_base_hyperlink=f"{V3_API_PREFIX}/files"
        )

        assert file.id == response.id
        assert file.filename == response.filename
        assert file.key == response.key
        assert file.owner_id == response.owner_id
        assert (
            response.hal_links.self.href == f"{V3_API_PREFIX}/files/{file.id}"
        )

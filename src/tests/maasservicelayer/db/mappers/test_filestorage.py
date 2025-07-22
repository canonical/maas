#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from maasservicelayer.builders.filestorage import FileStorageBuilder
from maasservicelayer.db.mappers.filestorage import FileStorageDomainDataMapper
from maasservicelayer.db.tables import FileStorageTable
from maasservicelayer.models.filestorage import FileStorage


class TestFileStorageDomainDataMapper:
    def test_build_resource(self):
        file = FileStorage(
            id=1,
            filename="abc.xyz",
            content=b"test file content",
            key="",
            owner_id=None,
        )

        mapper = FileStorageDomainDataMapper(FileStorageTable)
        builder = FileStorageBuilder(
            filename=file.filename,
            content=file.content,
            key=file.key,
            owner_id=file.owner_id,
        )

        result = mapper.build_resource(builder)

        # Ensure content is base64-encoded string, not bytes
        assert "content" in result
        assert result["content"] == "dGVzdCBmaWxlIGNvbnRlbnQ="

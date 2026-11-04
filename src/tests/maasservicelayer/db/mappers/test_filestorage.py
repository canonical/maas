#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from types import MappingProxyType

import pytest

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

        mapper = FileStorageDomainDataMapper(FileStorage, FileStorageTable)
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

    @pytest.mark.parametrize("content", [b"", b"\x00\xff\xfe", b"YWJj"])
    def test_roundtrip_preserves_bytes_and_input(self, content):
        mapper = FileStorageDomainDataMapper(FileStorage, FileStorageTable)
        builder = FileStorageBuilder(content=content)
        values = mapper.build_resource(builder).get_values()
        row = MappingProxyType(
            dict(id=1, filename="file", key="key", owner_id=None, **values)
        )
        original = dict(row)

        assert mapper.to_domain(row).content == content
        assert mapper.to_domain(row).content == content
        assert dict(row) == original
        assert builder.content == content

    def test_build_resource_without_content(self):
        mapper = FileStorageDomainDataMapper(FileStorage, FileStorageTable)

        resource = mapper.build_resource(FileStorageBuilder(filename="file"))

        assert resource.get_values() == {"filename": "file"}

# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib
from io import BufferedWriter
import os
from pathlib import Path
import shutil
import tarfile
from unittest.mock import MagicMock, Mock

import aiofiles
import aiofiles.os
from aiofiles.threadpool.binary import AsyncBufferedIOBase
import pytest

from maasservicelayer.utils.image_local_files import (
    AsyncLocalBootResourceFile,
    LocalStoreAllocationFail,
    LocalStoreFileSizeMismatch,
    LocalStoreInvalidHash,
    SyncLocalBootResourceFile,
)
from tests.fixtures import AsyncContextManagerMock, ContextManagerMock

FILE_SIZE = 1024
FILE_SLICE = 64


@pytest.fixture
def maas_data_dir(mocker, tmpdir):
    mocker.patch.dict(os.environ, {"MAAS_DATA": str(tmpdir)})
    yield tmpdir


@pytest.fixture
def image_store_dir(mocker, maas_data_dir):
    store = Path(maas_data_dir) / "image-storage"
    store.mkdir()
    yield store
    shutil.rmtree(store)


@pytest.fixture
def file_content() -> bytes:
    content = b"\x01" * FILE_SIZE
    yield content


@pytest.fixture
def file_sha256(file_content: bytes):
    sha256 = hashlib.sha256()
    sha256.update(file_content)
    yield str(sha256.hexdigest())


@pytest.fixture
def file_filename_on_disk(file_sha256: str):
    yield file_sha256[:7]


class TestAsyncLocalBootResourceFile:
    async def test_size_empty_file(self, image_store_dir):
        f = AsyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        # file does not exist on disk
        assert await f.size() == 0

    async def test_complete_empty_file(self, image_store_dir):
        f = AsyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        # file does not exist on disk
        assert not await f.complete()

    async def test_complete(self, image_store_dir, file_content):
        f = AsyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        async with aiofiles.open(f.path, "wb") as stream:
            await stream.write(file_content)

        assert await f.size() == FILE_SIZE
        assert await f.complete()

    async def test_valid(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = AsyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        async with aiofiles.open(f.path, "wb") as stream:
            await stream.write(file_content)

        assert await f.valid()

    async def test_unlink_nonexistent(self, image_store_dir):
        f = AsyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        # Should not raise exceptions
        await f.unlink()
        assert not f.path.exists()

    async def test_unlink_existent(self, image_store_dir):
        f = AsyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        f.path.touch()

        await f.unlink()
        assert not f.path.exists()

    async def test_store_no_space_left(self, image_store_dir, mocker):
        statvfs_mock = mocker.patch("aiofiles.os.statvfs")
        statvfs_result = Mock()
        statvfs_result.f_bavail = 0
        statvfs_result.f_frsize = 4096
        statvfs_mock.return_value = statvfs_result

        f = AsyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreAllocationFail):
            async with f.store() as store:
                await store.write(b"\x01")

    async def test_store_file_gets_truncated(
        self,
        image_store_dir,
        file_content,
        file_sha256,
        file_filename_on_disk,
        mocker,
    ):
        tmp_file = Mock(AsyncBufferedIOBase)
        tmp_file_ctx_manager = AsyncContextManagerMock(tmp_file)
        tmp_file.tell.return_value = FILE_SIZE
        mocker.patch(
            "aiofiles.open",
            return_value=tmp_file_ctx_manager,
        )

        f = AsyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        # We ignore the exception to avoid mocking  the `valid` method of the
        # `AsyncLocalBootResourceFile`
        with pytest.raises(LocalStoreInvalidHash):
            async with f.store() as store:
                await store.write(file_content)

        tmp_file.truncate.assert_called_once_with(FILE_SIZE)

    async def test_store_raises_if_size_less_than_total_size(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = AsyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreFileSizeMismatch):
            async with f.store() as store:
                await store.write(file_content[:-1])

        # unlink has been called
        assert not f.path.exists()

    async def test_store_raises_if_size_greater_than_total_size(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = AsyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreFileSizeMismatch):
            async with f.store() as store:
                await store.write(file_content)
                await store.write(b"\x01")

        # unlink has been called
        assert not f.path.exists()

    async def test_store_raises_if_sha_doesnt_match(
        self, image_store_dir, file_content, file_filename_on_disk
    ):
        f = AsyncLocalBootResourceFile(
            sha256="wrong-sha",
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreInvalidHash):
            async with f.store() as store:
                await store.write(file_content)

        # unlink has been called
        assert not f.path.exists()

    async def test_store_succeeds(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = AsyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        async with f.store() as store:
            await store.write(file_content)

        assert f.path.exists()

        async with aiofiles.open(f.path, "rb") as stream:
            content = await stream.read()

        assert content == file_content

    async def test_extract_file(
        self,
        image_store_dir,
        mocker,
    ):
        mock_mkdir = mocker.patch("os.mkdir")
        mock_tarfile = Mock(tarfile.TarFile)
        tar_ctx_manager_mock = ContextManagerMock(mock_tarfile)
        mocker.patch("tarfile.open", return_value=tar_ctx_manager_mock)
        f = AsyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="foo.tar",
            total_size=FILE_SIZE,
        )

        await f.extract_file("extract_dir")

        expected_dir = Path(image_store_dir / "extract_dir").absolute()
        # path mkdir is calling os.mkdir with mode 511
        mock_mkdir.assert_called_once_with(expected_dir, 511)
        mock_tarfile.extractall.assert_called_once()


class TestSyncLocalBootResourceFile:
    def test_size_empty_file(self, image_store_dir):
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        # file does not exist on disk
        assert f.size == 0

    def test_complete_empty_file(self, image_store_dir):
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        # file does not exist on disk
        assert not f.complete

    def test_complete(self, image_store_dir, file_content):
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        with open(f.path, "wb") as stream:
            stream.write(file_content)

        assert f.size == FILE_SIZE
        assert f.complete

    def test_valid(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = SyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        with open(f.path, "wb") as stream:
            stream.write(file_content)

        assert f.valid

    def test_unlink_nonexistent(self, image_store_dir):
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        # Should not raise exceptions
        f.unlink()
        assert not f.path.exists()

    def test_unlink_existent(self, image_store_dir):
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        f.path.touch()

        f.unlink()
        assert not f.path.exists()

    def test_store_no_space_left(self, image_store_dir, mocker):
        disk_usage_mock = mocker.patch("shutil.disk_usage")
        disk_usage_result = Mock()
        disk_usage_result.free = 0
        disk_usage_mock.return_value = disk_usage_result

        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreAllocationFail):
            with f.store() as store:
                store.write(b"\x01")

    def test_store_file_gets_truncated(
        self,
        image_store_dir,
        file_content,
        file_sha256,
        file_filename_on_disk,
        mocker,
    ):
        tmp_file = MagicMock(BufferedWriter)
        tmp_file_ctx_manager = ContextManagerMock(tmp_file)
        tmp_file.tell.return_value = FILE_SIZE
        mocker.patch("builtins.open", return_value=tmp_file_ctx_manager)

        f = SyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        # We ignore the exception to avoid mocking the `valid` method of the
        # `SyncLocalBootResourceFile`
        with pytest.raises(LocalStoreInvalidHash):
            with f.store() as store:
                store.write(file_content)

        tmp_file.truncate.assert_called_once_with(FILE_SIZE)

    def test_store_raises_if_size_less_than_total_size(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = SyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreFileSizeMismatch):
            with f.store() as store:
                store.write(file_content[:-1])

        # unlink has been called
        assert not f.path.exists()

    def test_store_raises_if_size_greater_than_total_size(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = SyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreFileSizeMismatch):
            with f.store() as store:
                store.write(file_content)
                store.write(b"\x01")

        # unlink has been called
        assert not f.path.exists()

    def test_store_raises_if_sha_doesnt_match(
        self, image_store_dir, file_content, file_filename_on_disk
    ):
        f = SyncLocalBootResourceFile(
            sha256="wrong-sha",
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreInvalidHash):
            with f.store() as store:
                store.write(file_content)

        # unlink has been called
        assert not f.path.exists()

    def test_store_succeeds(
        self, image_store_dir, file_content, file_sha256, file_filename_on_disk
    ):
        f = SyncLocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )

        with f.store() as store:
            store.write(file_content)

        assert f.path.exists()

        with open(f.path, "rb") as stream:
            content = stream.read()

        assert content == file_content

    def test_extract_file(
        self,
        image_store_dir,
        mocker,
    ):
        mock_mkdir = mocker.patch("os.mkdir")
        mock_tarfile = Mock(tarfile.TarFile)
        tar_ctx_manager_mock = ContextManagerMock(mock_tarfile)
        mocker.patch("tarfile.open", return_value=tar_ctx_manager_mock)
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="foo.tar",
            total_size=FILE_SIZE,
        )

        f.extract_file("extract_dir")

        expected_dir = Path(image_store_dir / "extract_dir").absolute()
        # path mkdir is calling os.mkdir with mode 511
        mock_mkdir.assert_called_once_with(expected_dir, 511)
        mock_tarfile.extractall.assert_called_once()

    def test_append_chunk_too_much_data(self, image_store_dir):
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreFileSizeMismatch):
            for _ in range(0, FILE_SIZE + FILE_SLICE, FILE_SLICE):
                f.append_chunk(b"\x01" * FILE_SLICE)

    def test_append_chunk_no_space_left_on_disk(
        self, image_store_dir, file_content, mocker
    ):
        mock_file = Mock(BufferedWriter)
        mock_file.tell.return_value = 0
        io_error = IOError()
        io_error.errno = 28
        mock_file.write.side_effect = io_error
        mocker.patch(
            "builtins.open", return_value=ContextManagerMock(mock_file)
        )
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        with pytest.raises(LocalStoreAllocationFail):
            for i in range(0, len(file_content), FILE_SLICE):
                f.append_chunk(file_content[i : i + FILE_SLICE])

    def test_append_chunk_other_io_error(
        self, image_store_dir, file_content, mocker
    ):
        mock_file = Mock(BufferedWriter)
        mock_file.tell.return_value = 0
        mock_file.write.side_effect = IOError()
        mocker.patch(
            "builtins.open", return_value=ContextManagerMock(mock_file)
        )
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        with pytest.raises(IOError):
            for i in range(0, len(file_content), FILE_SLICE):
                f.append_chunk(file_content[i : i + FILE_SLICE])

    def test_append_chunk(self, image_store_dir, file_content):
        f = SyncLocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )

        for i in range(0, len(file_content), FILE_SLICE):
            f.append_chunk(file_content[i : i + FILE_SLICE])

import hashlib
from io import BytesIO
from itertools import islice, repeat
import os
from pathlib import Path
import shutil
from typing import BinaryIO

import pytest

from maasserver.utils.bootresource import (
    LocalBootResourceFile,
    LocalStoreAllocationFail,
    LocalStoreInvalidHash,
    LocalStoreWriteBeyondEOF,
)

FILE_SIZE = 1 << 10
FILE_SLICE = 1 << 6


@pytest.fixture
def maas_data_dir(mocker, tmpdir):
    mocker.patch.dict(os.environ, {"MAAS_DATA": str(tmpdir)})
    yield tmpdir


@pytest.fixture
def image_store_dir(mocker, maas_data_dir):
    store = Path(maas_data_dir) / "boot-resources"
    store.mkdir()
    yield store
    shutil.rmtree(store)


@pytest.fixture
def file_content() -> BinaryIO:
    zeroes = repeat(b"\x01")
    content = b"".join(islice(zeroes, FILE_SIZE))
    yield BytesIO(content)


@pytest.fixture
def file_sha256(file_content: BinaryIO):
    sha256 = hashlib.sha256()
    for data in file_content:
        sha256.update(data)
    file_content.seek(0, os.SEEK_SET)  # rewind
    yield str(sha256.hexdigest())


class TestLocalBootResourceFile:
    def test_path_complete_file(self, image_store_dir: Path):
        f = LocalBootResourceFile(sha256="cadecafe", total_size=FILE_SIZE)
        assert f.path == image_store_dir / "cadecafe"

    def test_path_incomplete_file(self, image_store_dir: Path):
        f = LocalBootResourceFile(sha256="cadecafe", total_size=FILE_SIZE)
        assert f.partial_file_path == image_store_dir / "cadecafe.incomplete"

    def test_complete(self, image_store_dir: Path):
        with open(image_store_dir / "cadecafe", "wb") as stream:
            stream.seek(FILE_SIZE - 1, os.SEEK_SET)
            stream.write(b"\0")
        f = LocalBootResourceFile(sha256="cadecafe", total_size=FILE_SIZE)
        assert f.size == FILE_SIZE
        assert f.complete

    def test_incomplete(self, image_store_dir: Path):
        with open(image_store_dir / "cadecafe.incomplete", "wb") as stream:
            stream.write(b"\0")
        f = LocalBootResourceFile(sha256="cadecafe", total_size=FILE_SIZE)
        assert not f.complete

    def test_commit(self, image_store_dir: Path):
        open(image_store_dir / "cadecafe.incomplete", "wb").close()

        f = LocalBootResourceFile(sha256="cadecafe", total_size=FILE_SIZE)
        f.commit()
        assert not os.access(f.partial_file_path, os.F_OK)
        assert os.access(f.path, os.F_OK)

    def test_unlink(self, image_store_dir: Path):
        # both files existing at the same time is unexpected, but calling
        # unlink() should fix this
        open(image_store_dir / "cadecafe.incomplete", "wb").close()
        open(image_store_dir / "cadecafe", "wb").close()

        f = LocalBootResourceFile(sha256="cadecafe", total_size=FILE_SIZE)
        f.unlink()
        assert not os.access(f.partial_file_path, os.F_OK)
        assert not os.access(f.path, os.F_OK)

    def test_valid(
        self, image_store_dir: Path, file_content: BinaryIO, file_sha256: str
    ):
        with open(image_store_dir / file_sha256, "wb") as stream:
            for data in file_content:
                stream.write(data)
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE)
        assert f.valid

    def test_valid_not_ok(self, image_store_dir: Path, file_content: BinaryIO):
        with open(image_store_dir / "invalidhash", "wb") as stream:
            for data in file_content:
                stream.write(data)
        f = LocalBootResourceFile(sha256="invalidhash", total_size=FILE_SIZE)
        assert not f.valid

    def test_allocate(self, image_store_dir: Path, file_sha256: str):
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE)
        f.allocate()
        st = f.partial_file_path.stat()
        assert st.st_size == FILE_SIZE

    def test_allocate_raise_error(
        self, image_store_dir: Path, file_content: BinaryIO, file_sha256: str
    ):
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE)
        with f.path.open("wb") as stream:
            stream.write(file_content.read())
        with pytest.raises(LocalStoreAllocationFail):
            f.allocate()

    def test_store(
        self, image_store_dir: Path, file_content: BinaryIO, file_sha256: str
    ):
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE)
        assert f.store(file_content)
        assert os.access(f.path, os.F_OK)
        assert f.valid

    def test_store_append(
        self, image_store_dir: Path, file_content: BinaryIO, file_sha256: str
    ):
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE)
        while slice := file_content.read(FILE_SLICE):
            buf = BytesIO(slice)
            f.store(buf)
        assert os.access(f.path, os.F_OK)
        assert f.valid

    def test_store_beyond_eof(
        self, image_store_dir: Path, file_content: BinaryIO, file_sha256: str
    ):
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE - 1)
        with pytest.raises(LocalStoreWriteBeyondEOF):
            while slice := file_content.read(FILE_SLICE):
                buf = BytesIO(slice)
                f.store(buf)

    def test_store_corrupt_file(
        self, image_store_dir: Path, file_content: BinaryIO
    ):
        f = LocalBootResourceFile(sha256="invalidhash", total_size=FILE_SIZE)
        with pytest.raises(LocalStoreInvalidHash):
            f.store(file_content)
        assert not os.access(f.path, os.F_OK)
        assert os.access(f.partial_file_path, os.F_OK)
        assert not f.valid

    def test_create_from_content(
        self,
        image_store_dir: Path,
        file_content: BinaryIO,
        file_sha256: str,
    ):
        f = LocalBootResourceFile.create_from_content(file_content)
        assert os.access(f.path, os.F_OK)
        assert f.valid
        assert f.size == FILE_SIZE
        assert f.sha256 == file_sha256

    def test_lock_acquire(self, image_store_dir: Path, file_sha256: str):
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE)
        assert f.acquire_lock()
        f.release_lock()

    def test_lock_acquire_try(self, image_store_dir: Path, file_sha256: str):
        f = LocalBootResourceFile(sha256=file_sha256, total_size=FILE_SIZE)
        assert f.acquire_lock(try_lock=True)
        f.release_lock()

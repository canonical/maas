import hashlib
from io import BytesIO
from itertools import islice, repeat
import os
from pathlib import Path
import shutil

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
    store = Path(maas_data_dir) / "image-storage"
    store.mkdir()
    yield store
    shutil.rmtree(store)


@pytest.fixture
def file_content() -> bytes:
    ones = repeat(b"\x01")
    content = bytes(b"".join(islice(ones, FILE_SIZE)))
    yield content


@pytest.fixture
def file_sha256(file_content: bytes):
    sha256 = hashlib.sha256()
    sha256.update(file_content)
    yield str(sha256.hexdigest())


@pytest.fixture
def file_filename_on_disk(file_sha256: str):
    yield file_sha256[:7]


class TestLocalBootResourceFile:
    def test_path_complete_file(self, image_store_dir: Path):
        f = LocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        assert f.path == image_store_dir / "cadecafe"

    def test_path_incomplete_file(self, image_store_dir: Path):
        f = LocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        assert f.partial_file_path == image_store_dir / "cadecafe.incomplete"

    def test_complete(self, image_store_dir: Path):
        with open(image_store_dir / "cadecafe", "wb") as stream:
            stream.seek(FILE_SIZE - 1, os.SEEK_SET)
            stream.write(b"\0")
        f = LocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        assert f.size == FILE_SIZE
        assert f.complete

    def test_incomplete(self, image_store_dir: Path):
        with open(image_store_dir / "cadecafe.incomplete", "wb") as stream:
            stream.write(b"\0")
        f = LocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        assert not f.complete

    def test_commit(self, image_store_dir: Path):
        open(image_store_dir / "cadecafe.incomplete", "wb").close()

        f = LocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        f.commit()
        assert not os.access(f.partial_file_path, os.F_OK)
        assert os.access(f.path, os.F_OK)

    def test_unlink(self, image_store_dir: Path):
        # both files existing at the same time is unexpected, but calling
        # unlink() should fix this
        open(image_store_dir / "cadecafe.incomplete", "wb").close()
        open(image_store_dir / "cadecafe", "wb").close()

        f = LocalBootResourceFile(
            sha256="cadecafe",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        f.unlink()
        assert not os.access(f.partial_file_path, os.F_OK)
        assert not os.access(f.path, os.F_OK)

    def test_valid(
        self,
        image_store_dir: Path,
        file_content: bytes,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        with open(image_store_dir / file_filename_on_disk, "wb") as stream:
            stream.write(file_content)
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        assert f.valid

    def test_valid_not_ok(self, image_store_dir: Path, file_content: bytes):
        with open(image_store_dir / "invalidhash", "wb") as stream:
            stream.write(file_content)
        f = LocalBootResourceFile(
            sha256="invalidhash",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        assert not f.valid

    def test_allocate(
        self,
        image_store_dir: Path,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        f.allocate()
        st = f.partial_file_path.stat()
        assert st.st_size == FILE_SIZE

    def test_allocate_raise_error(
        self,
        image_store_dir: Path,
        file_content: bytearray,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
            size=1,
        )
        with pytest.raises(LocalStoreAllocationFail):
            f.allocate()

    def test_allocate_truncates_rogue_file(
        self,
        image_store_dir: Path,
        file_content: bytearray,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        with f.path.open("wb") as stream:
            stream.write(b"random_content")
        f.allocate()
        st = f.partial_file_path.stat()
        assert st.st_size == FILE_SIZE

    def test_store(
        self,
        image_store_dir: Path,
        file_content: bytes,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        with f.store() as mm:
            mm.write(file_content)
        assert os.access(f.path, os.F_OK)
        assert f.valid

    def test_store_append(
        self,
        image_store_dir: Path,
        file_content: bytes,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        for s in islice(file_content, None, None, FILE_SLICE):
            with f.store() as mm:
                mm.write(file_content[s : s + FILE_SLICE])
        assert os.access(f.path, os.F_OK)
        assert f.valid

    def test_store_beyond_eof(
        self,
        image_store_dir: Path,
        file_content: bytes,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE - 1,
        )
        with pytest.raises(LocalStoreWriteBeyondEOF):
            for s in islice(file_content, None, None, FILE_SLICE):
                with f.store() as mm:
                    mm.write(file_content[s : s + FILE_SLICE])

    def test_store_corrupt_file(
        self, image_store_dir: Path, file_content: bytes
    ):
        f = LocalBootResourceFile(
            sha256="invalidhash",
            filename_on_disk="cadecafe",
            total_size=FILE_SIZE,
        )
        with pytest.raises(LocalStoreInvalidHash):
            with f.store() as mm:
                mm.write(file_content)
        assert not os.access(f.path, os.F_OK)
        assert os.access(f.partial_file_path, os.F_OK)
        assert not f.valid

    def test_create_from_content(
        self,
        image_store_dir: Path,
        file_content: bytes,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        with LocalBootResourceFile.create_from_content(
            BytesIO(file_content)
        ) as (tmpname, size, sha256):
            localfile = LocalBootResourceFile(sha256, sha256[:7], size)
            if not localfile.path.exists():
                os.link(tmpname, localfile.path)
        assert os.access(localfile.path, os.F_OK)
        assert localfile.valid
        assert localfile.size == FILE_SIZE
        assert localfile.sha256 == file_sha256
        assert localfile.filename_on_disk == file_sha256[:7]

    def test_lock_acquire(
        self,
        image_store_dir: Path,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        assert f.acquire_lock()
        f.release_lock()

    def test_lock_acquire_try(
        self,
        image_store_dir: Path,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        assert f.acquire_lock(try_lock=True)
        f.release_lock()

    def test_lock_path(
        self,
        image_store_dir: Path,
        file_sha256: str,
        file_filename_on_disk: str,
    ):
        f = LocalBootResourceFile(
            sha256=file_sha256,
            filename_on_disk=file_filename_on_disk,
            total_size=FILE_SIZE,
        )
        assert f.lock_file.name.startswith("maas:bootres_")

# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with local boot resources."""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
import fcntl
import hashlib
import mmap
import os
from pathlib import Path
import tarfile
from tempfile import NamedTemporaryFile
from typing import BinaryIO

import aiofiles

from provisioningserver.path import get_maas_data_path, get_maas_lock_path

CHUNK_SIZE = 4 * (2**20)

BOOTLOADERS_DIR = "bootloaders"


class LocalStoreWriteBeyondEOF(Exception):
    """Attempt to write beyond EOF"""


class LocalStoreInvalidHash(Exception):
    """File SHA256 checksum has failed"""


class LocalStoreAllocationFail(Exception):
    """Could not allocate space for this file"""


class LocalStoreLockException(Exception):
    """Could not acquire file lock"""


def get_bootresource_store_path() -> Path:
    return Path(get_maas_data_path("image-storage"))


class MMapedLocalFile(mmap.mmap):
    def __new__(cls, lfile: LocalBootResourceFile, fileno: int):
        obj = super().__new__(cls, fileno=fileno, length=lfile.total_size)
        obj.lfile = lfile
        return obj

    def write(self, content: bytes) -> int:
        self._check_content_size(content)
        try:
            wrote = super().write(content)
            self.lfile._size = self.tell()
            return wrote
        except ValueError as e:
            raise LocalStoreWriteBeyondEOF(e)

    def _check_content_size(self, content):
        """Check if `content` fits in the file

        This works only for "seekable" contents

        Args:
            content (Buffer): The content to be written

        Raises:
            LocalStoreWriteBeyondEOF: Content too big
        """
        if hasattr(content, "seekable") and content.seekable():
            to_write = content.seek(0, os.SEEK_END)  # type: ignore[attr-defined]
            if self.lfile._size + to_write > self.lfile.total_size:
                msg = (
                    "Attempt to write beyond EOF, current "
                    f"{self.lfile._size}/{self.lfile.total_size}, new {to_write}"
                )
                raise LocalStoreWriteBeyondEOF(msg)
            content.seek(0, os.SEEK_SET)  # type: ignore[attr-defined]


class LocalBootResourceFile:
    def __init__(self, sha256: str, total_size: int, size: int = 0) -> None:
        """Local boot resource file

        Args:
            sha256 (str): the file SHA256 checksum
            total_size (int): the complete file size, in bytes
            size (int, optional): the current file size, in bytes. Defaults to 0.
        """
        self.sha256 = sha256
        self.total_size = total_size
        self._size = size
        self._base_path = get_bootresource_store_path() / self.sha256
        self._lock_fd: int | None = None

    def __repr__(self):
        return f"<LocalBootResourceFile {self.sha256} {self._size}/{self.total_size}>"

    @property
    def path(self) -> Path:
        """The file path in the image store

        Returns:
            Path: Path object
        """
        return self._base_path

    @property
    def partial_file_path(self) -> Path:
        """The file temporary path

        Returns:
            Path: Path object
        """
        return self._base_path.with_suffix(".incomplete")

    def _get_file_path(self) -> Path | None:
        for p in [self.path, self.partial_file_path]:
            if p.exists():
                return p
        return None

    @property
    def size(self) -> int:
        """The file actual size

        Returns:
            int: file size in bytes
        """
        if self._size == 0 and self.path.exists():
            self._size = self.total_size
        return self._size

    @property
    def complete(self):
        """`content` has been completely saved."""
        return self.size == self.total_size

    @property
    def valid(self):
        """All content has been written and stored SHA256 value is the same
        as the calculated SHA256 value stored in the database.

        Note: Depending on the size of the file, this can take some time.

        Returns:
            bool: Whether the file is valid
        """
        if not self.complete:
            return False
        if p := self._get_file_path():
            sha256 = hashlib.sha256()
            with p.open("rb") as stream:
                for data in stream:
                    sha256.update(data)
            hexdigest = sha256.hexdigest()
            return hexdigest == self.sha256
        return False

    async def avalid(self) -> bool:
        """Async version of `valid` (see above)

        Returns:
            bool: Whether the file is valid
        """
        if not self.complete:
            return False
        if p := self._get_file_path():
            sha256 = hashlib.sha256()
            async with aiofiles.open(p, "rb") as stream:
                while data := await stream.read(CHUNK_SIZE):
                    sha256.update(data)
            hexdigest = sha256.hexdigest()
            return hexdigest == self.sha256
        return False

    def commit(self) -> bool:
        """Moves the file to the final destination

        Returns:
            bool: Whether the file was successfully moved
        """
        if self.partial_file_path.exists():
            self.partial_file_path.rename(self.path)
        return True

    def allocate(self):
        """Allocates disk space for this file"""
        if self._size > 0:
            raise LocalStoreAllocationFail("File already exists")
        try:
            with self.partial_file_path.open("wb") as stream:
                stream.seek(self.total_size - 1, os.SEEK_SET)
                stream.write(b"\x00")
                stream.flush()
        except IOError as e:
            raise LocalStoreAllocationFail(e)

    @contextmanager
    def store(self, autocommit: bool = True) -> MMapedLocalFile:
        """Store file in the local disk

        Args:
            autocommit (bool, optional): whether the file should be validated
                when complete. Defaults to True.

        Raises:
            LocalStoreWriteBeyondEOF: content doesn't fit in the file
            LocalStoreInvalidHash: SHA256 checksum failed

        Returns:
            bool: Whether the file is complete
        """
        if self._size == 0:
            self.allocate()
        elif self.complete:
            raise LocalStoreWriteBeyondEOF()

        with self.partial_file_path.open("rb+") as stream, MMapedLocalFile(
            fileno=stream.fileno(),
            lfile=self,
        ) as mm:
            mm.seek(self._size, os.SEEK_SET)
            yield mm
        if autocommit and self.complete:
            if self.valid:
                self.commit()
            else:
                raise LocalStoreInvalidHash()

    @asynccontextmanager
    async def astore(self, autocommit: bool = True) -> MMapedLocalFile:
        """Store file in the local disk (async)

        Args:
            autocommit (bool, optional): whether the file should be validated
                when complete. Defaults to True.

        Raises:
            LocalStoreWriteBeyondEOF: content doesn't fit in the file
            LocalStoreInvalidHash: SHA256 checksum failed

        Returns:
            bool: Whether the file is complete
        """
        if self._size == 0:
            self.allocate()
        elif self.complete:
            raise LocalStoreWriteBeyondEOF()

        with self.partial_file_path.open("rb+") as stream, MMapedLocalFile(
            fileno=stream.fileno(),
            lfile=self,
        ) as mm:
            mm.seek(self._size, os.SEEK_SET)
            yield mm
        if autocommit and self.complete:
            if await self.avalid():
                self.commit()
            else:
                raise LocalStoreInvalidHash()

    def unlink(self):
        """Removes the file from local disk"""
        self._size = 0
        for p in [self.path, self.partial_file_path]:
            p.unlink(missing_ok=True)

    @property
    def lock_file(self) -> Path:
        return get_maas_lock_path() / f"bootres_{self.sha256}.lock"

    def acquire_lock(self, try_lock: bool = False) -> bool:
        if self._lock_fd is None:
            self._lock_fd = os.open(
                self.lock_file, os.O_RDWR | os.O_CREAT | os.O_TRUNC
            )
        flags = fcntl.LOCK_EX
        if try_lock:
            flags |= fcntl.LOCK_NB
        try:
            fcntl.flock(self._lock_fd, flags)
            return True
        except (BlockingIOError, PermissionError):
            return False

    def release_lock(self):
        if self._lock_fd is None:
            return
        fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
        os.close(self._lock_fd)
        self._lock_fd = None

    def __del__(self):
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(self._lock_fd)

    @contextmanager
    def lock(self):
        """File lock context manager"""
        try:
            self.acquire_lock()
            yield
        finally:
            self.release_lock()

    @classmethod
    def create_from_content(
        cls,
        content: BinaryIO,
    ):
        """Create a local file from content.
        This method assumes that content was externally validated already

        Args:
            content (BinaryIO): the content to be written

        Returns:
            LocalBootResourceFile: the local file object
        """
        with NamedTemporaryFile(
            mode="+wb",
            dir=get_bootresource_store_path(),
        ) as tmp:
            sha256 = hashlib.sha256()
            for data in content:
                sha256.update(data)
                tmp.write(data)
            size = tmp.tell()
            hexdigest = sha256.hexdigest()
            localfile = cls(hexdigest, size)
            if not localfile.path.exists():
                os.link(tmp.name, localfile.path)
            return localfile

    def extract_file(self, extract_path: str):
        store = get_bootresource_store_path()
        target_dir = store / extract_path
        target_dir.mkdir(exist_ok=True, parents=True)
        with tarfile.open(self.path, mode="r") as tar:
            tar.extractall(
                path=target_dir.absolute(), filter=tarfile.tar_filter
            )

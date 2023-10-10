# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with local boot resources."""
from contextlib import contextmanager
import fcntl
import hashlib
import mmap
import os
from pathlib import Path
from typing import BinaryIO

from provisioningserver.path import get_maas_data_path


class LocalStoreWriteBeyondEOF(Exception):
    """Attempt to write beyond EOF"""


class LocalStoreInvalidHash(Exception):
    """File SHA256 checksum has failed"""


class LocalStoreAllocationFail(Exception):
    """Could not allocate space for this file"""


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
        self._base_path = (
            Path(get_maas_data_path("boot-resources")) / self.sha256
        )

    def __str__(self):
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
            if os.access(p, os.F_OK):
                return p
        return None

    @property
    def size(self) -> int:
        """The file actual size

        Returns:
            int: file size in bytes
        """
        if self._size == 0 and os.access(self.path, os.F_OK):
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

    def commit(self) -> bool:
        """Moves the file to the final destination

        Returns:
            bool: Whether the file was successfully moved
        """
        if os.access(self.partial_file_path, os.F_OK):
            self.partial_file_path.rename(self.path)
        return True

    def allocate(self):
        """Allocates disk space for this file"""
        if self.size > 0:
            raise LocalStoreAllocationFail("File already exists")
        try:
            with self.partial_file_path.open("wb") as stream:
                stream.seek(self.total_size - 1, os.SEEK_SET)
                stream.write(b"\x00")
                stream.flush()
        except IOError as e:
            raise LocalStoreAllocationFail(e)

    def store(self, content: BinaryIO, autocommit: bool = True) -> bool:
        """Store file in the local disk

        Args:
            content (BinaryIO): the file content
            autocommit (bool, optional): whether the file should be validated
                when complete. Defaults to True.

        Raises:
            LocalStoreWriteBeyondEOF: content doesn't fit in the file
            LocalStoreInvalidHash: SHA256 checksum failed

        Returns:
            bool: Whether the file is complete
        """
        if content.seekable():
            content_len = content.seek(0, os.SEEK_END)
            if self._size + content_len > self.total_size:
                msg = f"Attempt to write beyond EOF, current {self._size}/{self.total_size}, new {content_len}"
                raise LocalStoreWriteBeyondEOF(msg)
            content.seek(0, os.SEEK_SET)
        if self._size == 0:
            self.allocate()
        with self.partial_file_path.open("rb+") as stream, mmap.mmap(
            stream.fileno(), self.total_size
        ) as mm:
            mm.seek(self._size, os.SEEK_SET)
            for data in content:
                mm.write(data)
            self._size = mm.tell()
        if autocommit:
            if self.complete:
                if self.valid:
                    return self.commit()
                else:
                    raise LocalStoreInvalidHash()
            return False
        else:
            return self.complete

    def unlink(self):
        """Removes the file from local disk"""
        self._size = 0
        for p in [self.path, self.partial_file_path]:
            p.unlink(missing_ok=True)

    @contextmanager
    def lock(self):
        lock_file = self.path.with_suffix(".lock")
        open_flags = os.O_RDWR | os.O_CREAT | os.O_TRUNC
        fd = os.open(lock_file, open_flags)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError:
            os.close(fd)
            raise
        else:
            yield
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

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
        sha256 = hashlib.sha256()
        for data in content:
            sha256.update(data)
        hexdigest = sha256.hexdigest()
        total_size = content.tell()
        content.seek(0, os.SEEK_SET)

        localfile = cls(hexdigest, total_size)
        if not localfile.complete:
            localfile.store(content)
        return localfile

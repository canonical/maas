# Copyright 2023-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with local boot resources."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, contextmanager
import hashlib
from io import BufferedWriter
import os
import shutil
import tarfile
from typing import AsyncGenerator, Generator

import aiofiles
import aiofiles.os
from aiofiles.threadpool.binary import AsyncBufferedIOBase

from maascommon.utils.images import get_bootresource_store_path

CHUNK_SIZE = 4 * (2**20)


class LocalStoreException(Exception):
    """Base class for local store exceptions."""


class LocalStoreFileSizeMismatch(LocalStoreException):
    """Data received is greater than or less than expected file size"""


class LocalStoreInvalidHash(LocalStoreException):
    """File SHA256 checksum has failed"""


class LocalStoreAllocationFail(LocalStoreException):
    """Could not allocate space for this file"""


class SyncLocalBootResourceFile:
    def __init__(
        self,
        sha256: str,
        filename_on_disk: str,
        total_size: int,
    ) -> None:
        """Synchronous implementation of a local boot resource file.

        Args:
            sha256 (str): the file SHA256 checksum
            filename_on_disk (str): the name of the file on disk
            total_size (int): the complete file size, in bytes
        """
        self.sha256 = sha256
        self.filename_on_disk = filename_on_disk
        self.total_size = total_size
        self.path = get_bootresource_store_path() / self.filename_on_disk

    def __repr__(self):
        return f"<SyncLocalBootResourceFile {self.sha256} {self.filename_on_disk} {self.size}/{self.total_size}>"

    @property
    def size(self) -> int:
        try:
            return os.stat(self.path).st_size
        except FileNotFoundError:
            return 0

    @property
    def complete(self) -> bool:
        return self.size == self.total_size

    @property
    def valid(self) -> bool:
        if not self.complete:
            return False
        sha256 = hashlib.sha256()
        with open(self.path, "rb") as stream:
            while data := stream.read(CHUNK_SIZE):
                sha256.update(data)
        hexdigest = sha256.hexdigest()
        return hexdigest == self.sha256

    def append_chunk(self, data):
        """Append chunk of data to the file.

        Args:
            data: data to be written at the end of file
        Raises:
            LocalStoreFileSizeMismatch: if the data would exceed the total file size.
        """
        try:
            with open(self.path, "ab") as f:
                if f.tell() + len(data) > self.total_size:
                    self.unlink()
                    raise LocalStoreFileSizeMismatch()
                f.write(data)
        except IOError as e:
            self.unlink()
            if e.errno == 28:
                # We ran out of space
                raise LocalStoreAllocationFail() from e
            raise e

    @contextmanager
    def store(self) -> Generator[BufferedWriter]:
        """Store file in the local disk.

        Yields a file for writing data. On context manager exit, it checks
        whether the file is complete and if the SHA matches.

        Raises:
            LocalStoreInvalidHash: SHA256 checksum failed
            LocalStoreAllocationFail: no sufficient free disk space
            LocalStoreFileSizeMismatch: content written doesn't match the expected total size
        Yields:
            The file to write data to.
        """
        free = shutil.disk_usage(self.path.parent).free
        if free < self.total_size:
            raise LocalStoreAllocationFail()

        with open(self.path, "wb") as f:
            f.truncate(self.total_size)
            yield f
            if f.tell() != self.total_size:
                self.unlink()
                raise LocalStoreFileSizeMismatch()

        if not self.valid:
            self.unlink()
            raise LocalStoreInvalidHash()

    def extract_file(self, extract_path: str):
        store = get_bootresource_store_path()
        target_dir = store / extract_path
        target_dir.mkdir(exist_ok=True, parents=True)
        with tarfile.open(self.path, mode="r") as tar:
            tar.extractall(
                path=target_dir.absolute(), filter=tarfile.tar_filter
            )

    def unlink(self):
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass


class AsyncLocalBootResourceFile:
    def __init__(
        self,
        sha256: str,
        filename_on_disk: str,
        total_size: int,
    ) -> None:
        """Asynchronous implementation of a local boot resource file.

        Args:
            sha256 (str): the file SHA256 checksum
            filename_on_disk (str): the name of the file on disk
            total_size (int): the complete file size, in bytes
        """
        self.sha256 = sha256
        self.filename_on_disk = filename_on_disk
        self.total_size = total_size
        self.path = get_bootresource_store_path() / self.filename_on_disk

    async def size(self) -> int:
        try:
            return (await aiofiles.os.stat(self.path)).st_size
        except FileNotFoundError:
            return 0

    async def complete(self):
        """`content` has been completely saved."""
        return await self.size() == self.total_size

    async def valid(self) -> bool:
        """Async version of `valid` (see above)

        Returns:
            bool: Whether the file is valid
        """
        if not await self.complete():
            return False

        def calculate_sha256():
            sha256 = hashlib.sha256()
            with open(self.path, "rb") as stream:
                while data := stream.read(CHUNK_SIZE):
                    sha256.update(data)
            return sha256.hexdigest()

        hexdigest = await asyncio.get_running_loop().run_in_executor(
            None, calculate_sha256
        )
        return hexdigest == self.sha256

    @asynccontextmanager
    async def store(self) -> AsyncGenerator[AsyncBufferedIOBase]:
        """Store file in the local disk (async)

        Yields a file for writing data. On context manager exit, it checks
        whether the file is complete and if the SHA matches.

        Raises:
            LocalStoreInvalidHash: SHA256 checksum failed
            LocalStoreAllocationFail: no sufficient free disk space
            LocalStoreFileSizeMismatch: content written doesn't match the expected total size
        Yields:
            The file to write data to.
        """
        # shutil is synchronous, we calculate the free space as shutil would do
        # but asynchronously. See shutil.disk_usage.
        st = await aiofiles.os.statvfs(self.path.parent)
        free = st.f_bavail * st.f_frsize
        if free < self.total_size:
            raise LocalStoreAllocationFail()

        async with aiofiles.open(self.path, "wb") as file:
            await file.truncate(self.total_size)
            yield file
            if await file.tell() != self.total_size:
                await self.unlink()
                raise LocalStoreFileSizeMismatch()

        if not await self.valid():
            await self.unlink()
            raise LocalStoreInvalidHash()

    async def extract_file(self, extract_path: str):
        def sync_extract_file():
            store = get_bootresource_store_path()
            target_dir = store / extract_path
            target_dir.mkdir(exist_ok=True, parents=True)
            with tarfile.open(self.path, mode="r") as tar:
                tar.extractall(
                    path=target_dir.absolute(), filter=tarfile.tar_filter
                )

        return asyncio.get_running_loop().run_in_executor(
            None, sync_extract_file
        )

    async def unlink(self):
        """Removes the file from local disk"""
        try:
            await aiofiles.os.unlink(self.path)
        except FileNotFoundError:
            pass

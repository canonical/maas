# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


class ChunkBuffer:
    def __init__(self, max_size: int):
        self._buffer = bytearray()
        self._size = 0
        self._max_size = max_size

    def append_and_check(self, chunk: bytes) -> bool:
        """Returns True if the buffer is ready to be flushed, False otherwise."""
        self._buffer.extend(chunk)
        self._size += len(chunk)
        return self._size >= self._max_size

    def get_and_reset(self) -> bytearray:
        """Returns the content of the buffer and resets it."""
        buffer = self._buffer
        self._buffer = bytearray()
        self._size = 0
        return buffer

    def is_empty(self) -> bool:
        return self._size == 0

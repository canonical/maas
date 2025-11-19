# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.utils.buffer import ChunkBuffer

MAX_SIZE = 1024


class TestChunkBuffer:
    def test_is_empty(self):
        c = ChunkBuffer(MAX_SIZE)
        assert c.is_empty()

    def test_append_and_check_no_flush(self):
        c = ChunkBuffer(MAX_SIZE)
        assert not c.append_and_check(b"0" * (MAX_SIZE - 1))

    def test_append_and_check_flush(self):
        c = ChunkBuffer(MAX_SIZE)
        chunk_size = 64
        for _ in range(0, MAX_SIZE - chunk_size, chunk_size):
            assert not c.append_and_check(b"0" * chunk_size)

        assert c.append_and_check(b"0" * chunk_size)

    def test_get_and_reset(self):
        c = ChunkBuffer(MAX_SIZE)
        c.append_and_check(b"0" * 64)
        buffer = c.get_and_reset()
        assert buffer == b"0" * 64
        assert c.is_empty()

# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.utils.ulid import generate_ulid
from tests.utils.ulid import is_ulid


class TestUlid:
    def test_ulid_uniqueness_and_correctness(self, monkeypatch):
        ulids = {generate_ulid() for _ in range(100)}
        assert len(ulids) == 100  # Ensure all ULIDs are unique
        for u in ulids:
            assert is_ulid(u) is True

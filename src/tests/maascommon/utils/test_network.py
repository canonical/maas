#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from maascommon.utils.network import coerce_to_valid_hostname


class TestCoerceHostname:
    def test_replaces_international_characters(self):
        assert "abc-123" == coerce_to_valid_hostname("abc青い空123")

    def test_removes_illegal_dashes(self):
        assert "abc123" == coerce_to_valid_hostname("-abc123-")

    def test_replaces_whitespace_and_special_characters(self):
        assert "abc123-ubuntu" == coerce_to_valid_hostname("abc123 (ubuntu)")

    def test_makes_hostname_lowercase(self):
        assert "ubunturocks" == coerce_to_valid_hostname("UbuntuRocks")

    def test_preserve_hostname_case(self):
        assert "UbuntuRocks" == coerce_to_valid_hostname("UbuntuRocks", False)

    def test_returns_none_if_result_empty(self):
        assert coerce_to_valid_hostname("-人間性-") is None

    def test_returns_none_if_result_too_large(self):
        assert coerce_to_valid_hostname("a" * 65) is None

#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from netaddr import IPNetwork
import pytest

from maascommon.utils.network import (
    coerce_to_valid_hostname,
    MAASIPRange,
    MAASIPSet,
)


class TestMAASIPSet:
    @pytest.mark.parametrize(
        "cidr, used, unused",
        [
            (
                IPNetwork("10.0.0.0/31"),
                [],
                [MAASIPRange("10.0.0.0", "10.0.0.1")],
            ),
            (
                IPNetwork("10.0.0.0/32"),
                [],
                [MAASIPRange("10.0.0.0", "10.0.0.0")],
            ),
            (
                IPNetwork("10.0.0.0/24"),
                [MAASIPRange("10.0.0.1", "10.0.0.200")],
                [MAASIPRange("10.0.0.201", "10.0.0.254")],
            ),
            (
                IPNetwork("10.0.0.0/24"),
                [
                    MAASIPRange("10.0.0.1", "10.0.0.10"),
                    MAASIPRange("10.0.0.30", "10.0.0.40"),
                ],
                [
                    MAASIPRange("10.0.0.11", "10.0.0.29"),
                    MAASIPRange("10.0.0.41", "10.0.0.254"),
                ],
            ),
            (
                IPNetwork("10.0.0.0/24"),
                [MAASIPRange("10.0.0.1", "10.0.0.254")],
                [],
            ),
            (
                IPNetwork("2001:db8::/127"),
                [],
                [MAASIPRange("2001:db8::", "2001:db8::1")],
            ),
            (
                IPNetwork("2001:db8::/128"),
                [],
                [MAASIPRange("2001:db8::", "2001:db8::")],
            ),
            (
                IPNetwork("2001:db8::/64"),
                [MAASIPRange("2001:db8::", "2001:db8::10")],
                [MAASIPRange("2001:db8::11", "2001:db8::ffff:ffff:ffff:ffff")],
            ),
            (
                IPNetwork("2001:db8::/64"),
                [MAASIPRange("2001:db8::", "2001:db8::ffff:ffff:ffff:ffff")],
                [],
            ),
        ],
    )
    def test_get_unused_ranges_for_network(
        self,
        cidr: IPNetwork,
        used: list[MAASIPRange],
        unused: list[MAASIPRange],
    ) -> None:
        ip_set = MAASIPSet(used)
        unused_ip_set = ip_set.get_unused_ranges_for_network(cidr)
        assert unused_ip_set == MAASIPSet(unused)

    @pytest.mark.parametrize(
        "ranges, used, unused",
        [
            (
                [MAASIPRange("10.0.0.0", "10.0.0.1")],
                [],
                [MAASIPRange("10.0.0.0", "10.0.0.1")],
            ),
            (
                [MAASIPRange("10.0.0.0", "10.0.0.1")],
                [MAASIPRange("10.0.0.0", "10.0.0.1")],
                [],
            ),
            (
                [MAASIPRange("10.0.0.0", "10.0.0.1")],
                [MAASIPRange("10.0.0.0", "10.0.0.0")],
                [MAASIPRange("10.0.0.1", "10.0.0.1")],
            ),
            (
                [
                    MAASIPRange("10.0.0.1", "10.0.0.20"),
                    MAASIPRange("10.0.0.40", "10.0.0.50"),
                ],
                [MAASIPRange("10.0.0.1", "10.0.0.30")],
                [MAASIPRange("10.0.0.40", "10.0.0.50")],
            ),
            (
                [
                    MAASIPRange("10.0.0.1", "10.0.0.20"),
                    MAASIPRange("10.0.0.40", "10.0.0.50"),
                ],
                [
                    MAASIPRange("10.0.0.1", "10.0.0.10"),
                    MAASIPRange("10.0.0.40", "10.0.0.50"),
                ],
                [
                    MAASIPRange("10.0.0.11", "10.0.0.20"),
                ],
            ),
            (
                [MAASIPRange("2001:db8::", "2001:db8::1")],
                [],
                [MAASIPRange("2001:db8::", "2001:db8::1")],
            ),
            (
                [MAASIPRange("2001:db8::", "2001:db8::1")],
                [MAASIPRange("2001:db8::", "2001:db8::1")],
                [],
            ),
            (
                [MAASIPRange("2001:db8::", "2001:db8::1")],
                [MAASIPRange("2001:db8::", "2001:db8::")],
                [MAASIPRange("2001:db8::1", "2001:db8::1")],
            ),
            (
                [MAASIPRange("2001:db8::", "2001:db8::ff")],
                [
                    MAASIPRange("2001:db8::", "2001:db8::10"),
                    MAASIPRange("2001:db8::15", "2001:db8::20"),
                ],
                [
                    MAASIPRange("2001:db8::11", "2001:db8::14"),
                    MAASIPRange("2001:db8::21", "2001:db8::ff"),
                ],
            ),
        ],
    )
    def test_get_unused_ranges_for_range(
        self,
        ranges: list[MAASIPRange],
        used: list[MAASIPRange],
        unused: list[MAASIPRange],
    ) -> None:
        ip_set = MAASIPSet(used)
        unused_ip_set = ip_set.get_unused_ranges_for_range(ranges)
        assert unused_ip_set == MAASIPSet(unused)


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

# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_moonshot_autodetect.py."""

__all__ = []

from maastesting.testcase import MAASTestCase
from snippets import maas_moonshot_autodetect
from snippets.maas_moonshot_autodetect import get_ipmi_ip_address


class TestGetIPMIIPAddress(MAASTestCase):
    """Tests for get_ipmi_ip_address()."""

    scenarios = [
        ("none", dict(output="  IP Address  : \n\n", expected=None)),
        ("bogus", dict(output="  IP Address  : bogus\n\n", expected=None)),
        (
            "ipv4",
            dict(
                output="  IP Address  : 192.168.1.1\n\n",
                expected="192.168.1.1",
            ),
        ),
        (
            "ipv6",
            dict(
                output="  IP Address  : 2001:db8::3\n\n",
                expected="2001:db8::3",
            ),
        ),
        (
            "link-local",
            dict(output="  IP Address  : fe80::3:7\n\n", expected="fe80::3:7"),
        ),
    ]

    def test_get_ipmi_ip_address(self):
        getoutput = self.patch(
            maas_moonshot_autodetect.subprocess, "getoutput"
        )
        getoutput.return_value = self.output
        actual = get_ipmi_ip_address("127.0.0.1")
        self.assertEqual(self.expected, actual)

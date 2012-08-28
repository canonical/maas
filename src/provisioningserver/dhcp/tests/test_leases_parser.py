# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""..."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from collections import namedtuple
from datetime import datetime
from textwrap import dedent

from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.dhcp.leases_parser import (
    get_expiry_date,
    has_expired,
    parse_leases,
    )


class TestLeasesParser(TestCase):

    def fake_parsed_lease(self, ip=None, mac=None, ends=None):
        """Fake a lease as produced by the parser."""
        if ip is None:
            ip = factory.getRandomIPAddress()
        if mac is None:
            mac = factory.getRandomMACAddress()
        return namedtuple('lease', ['ip', 'mac', 'ends'])(ip, mac, ends)

    def test_get_expiry_date_parses_expiry_date(self):
        lease = self.fake_parsed_lease(ends='0 2011/01/02 03:04:05')
        self.assertEqual(
            datetime(
                year=2011, month=01, day=02,
                hour=03, minute=04, second=05),
            get_expiry_date(lease))

    def test_get_expiry_date_returns_None_for_never(self):
        self.assertIsNone(
            get_expiry_date(self.fake_parsed_lease(ends='never')))

    def test_get_expiry_date_returns_None_if_no_expiry_given(self):
        self.assertIsNone(get_expiry_date(self.fake_parsed_lease(ends=None)))

    def test_has_expired_returns_False_for_eternal_lease(self):
        now = datetime.utcnow()
        self.assertFalse(has_expired(self.fake_parsed_lease(ends=None), now))

    def test_has_expired_returns_False_for_future_expiry_date(self):
        now = datetime.utcnow()
        later = '1 2035/12/31 23:59:59'
        self.assertFalse(has_expired(self.fake_parsed_lease(ends=later), now))

    def test_has_expired_returns_True_for_past_expiry_date(self):
        now = datetime.utcnow()
        earlier = '1 2001/01/01 00:00:00'
        self.assertTrue(
            has_expired(self.fake_parsed_lease(ends=earlier), now))

    def test_parse_leases_copes_with_empty_file(self):
        self.assertEqual({}, parse_leases(""))

    def test_parse_leases_parses_lease(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            lease %(ip)s {
                starts 5 2010/01/01 00:00:01;
                ends never;
                tstp 6 2010/01/02 05:00:00;
                tsfp 6 2010/01/02 05:00:00;
                atsfp 6 2010/01/02 05:00:00;
                cltt 1 2010/01/02 05:00:00;
                binding state free;
                next binding state free;
                hardware ethernet %(mac)s;
                uid "\001\000\234\002\242\2020";
                set vendorclass = "PXEClient:Arch:00000:UNDI:002001";
                client-hostname foo;
                abandoned;
                option agent.circuit-id thing;
                option agent.remote-id thing;
                ddns-text foo;
                ddns-fwd-name foo;
                ddns-client-fqdn foo;
                ddns-rev-name foo;
                vendor-class-identifier foo;
                bootp;
                reserved;
            }
            """ % params))
        self.assertEqual({params['ip']: params['mac']}, leases)

    def test_parse_leases_ignores_incomplete_lease_at_end(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
            'incomplete_ip': factory.getRandomIPAddress(),
        }
        leases = parse_leases(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
            }
            lease %(incomplete_ip)s {
                starts 5 2010/01/01 00:00:05;
            """ % params))
        self.assertEqual({params['ip']: params['mac']}, leases)

    def test_parse_leases_ignores_comments(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            # Top comment (ignored).
            lease %(ip)s { # End-of-line comment (ignored).
                # Comment in lease block (ignored).
                hardware ethernet %(mac)s;  # EOL comment in lease (ignored).
            } # Comment right after closing brace (ignored).
            # End comment (ignored).
            """ % params))
        self.assertEqual({params['ip']: params['mac']}, leases)

    def test_parse_leases_ignores_expired_leases(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
                ends 1 2001/01/01 00:00:00;
            }
            """ % params))
        self.assertEqual({}, leases)

    def test_parse_leases_treats_never_as_eternity(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
                ends never;
            }
            """ % params))
        self.assertEqual({params['ip']: params['mac']}, leases)

    def test_parse_leases_treats_missing_end_date_as_eternity(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
            }
            """ % params))
        self.assertEqual({params['ip']: params['mac']}, leases)

    def test_parse_leases_takes_latest_lease_for_address(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'old_owner': factory.getRandomMACAddress(),
            'new_owner': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            lease %(ip)s {
                hardware ethernet %(old_owner)s;
            }
            lease %(ip)s {
                hardware ethernet %(new_owner)s;
            }
            """ % params))
        self.assertEqual({params['ip']: params['new_owner']}, leases)

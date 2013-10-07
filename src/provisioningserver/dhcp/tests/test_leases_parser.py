# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the DHCP leases parser."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import namedtuple
from datetime import datetime
from textwrap import dedent

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.dhcp.leases_parser import (
    combine_entries,
    gather_hosts,
    gather_leases,
    get_expiry_date,
    get_host_mac,
    has_expired,
    is_host,
    is_lease,
    lease_parser,
    parse_leases,
    )


class TestLeasesParser(MAASTestCase):

    def fake_parsed_lease(self, ip=None, mac=None, ends=None,
                          entry_type='lease'):
        """Fake a lease as produced by the parser."""
        if ip is None:
            ip = factory.getRandomIPAddress()
        if mac is None:
            mac = factory.getRandomMACAddress()
        Hardware = namedtuple('Hardware', ['mac'])
        Lease = namedtuple(
            'Lease', ['lease_or_host', 'ip', 'hardware', 'ends'])
        return Lease(entry_type, ip, Hardware(mac), ends)

    def fake_parsed_host(self, ip=None, mac=None):
        """Fake a host declaration as produced by the parser."""
        return self.fake_parsed_lease(ip=ip, mac=mac, entry_type='host')

    def fake_parsed_rubout(self, ip=None):
        """Fake a "rubout" host declaration."""
        if ip is None:
            ip = factory.getRandomIPAddress()
        Rubout = namedtuple('Rubout', ['lease_or_host', 'ip'])
        return Rubout('host', ip)

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

    def test_gather_leases_finds_current_leases(self):
        lease = self.fake_parsed_lease()
        self.assertEqual(
            {lease.ip: lease.hardware.mac},
            gather_leases([lease]))

    def test_gather_leases_ignores_expired_leases(self):
        earlier = '1 2001/01/01 00:00:00'
        lease = self.fake_parsed_lease(ends=earlier)
        self.assertEqual({}, gather_leases([lease]))

    def test_gather_leases_combines_expired_and_current_leases(self):
        earlier = '1 2001/01/01 00:00:00'
        ip = factory.getRandomIPAddress()
        old_owner = factory.getRandomMACAddress()
        new_owner = factory.getRandomMACAddress()
        leases = [
            self.fake_parsed_lease(ip=ip, mac=old_owner, ends=earlier),
            self.fake_parsed_lease(ip=ip, mac=new_owner),
            ]
        self.assertEqual({ip: new_owner}, gather_leases(leases))

    def test_gather_leases_ignores_ordering(self):
        earlier = '1 2001/01/01 00:00:00'
        ip = factory.getRandomIPAddress()
        old_owner = factory.getRandomMACAddress()
        new_owner = factory.getRandomMACAddress()
        leases = [
            self.fake_parsed_lease(ip=ip, mac=new_owner),
            self.fake_parsed_lease(ip=ip, mac=old_owner, ends=earlier),
            ]
        self.assertEqual({ip: new_owner}, gather_leases(leases))

    def test_gather_leases_ignores_host_declarations(self):
        self.assertEqual({}, gather_leases([self.fake_parsed_host()]))

    def test_gather_hosts_finds_hosts(self):
        host = self.fake_parsed_host()
        self.assertEqual({host.ip: host.hardware.mac}, gather_hosts([host]))

    def test_gather_hosts_ignores_unaccompanied_rubouts(self):
        self.assertEqual({}, gather_hosts([self.fake_parsed_rubout()]))

    def test_gather_hosts_ignores_rubbed_out_entries(self):
        ip = factory.getRandomIPAddress()
        hosts = [
            self.fake_parsed_host(ip=ip),
            self.fake_parsed_rubout(ip=ip),
            ]
        self.assertEqual({}, gather_hosts(hosts))

    def test_gather_hosts_follows_reassigned_host(self):
        ip = factory.getRandomIPAddress()
        new_owner = factory.getRandomMACAddress()
        hosts = [
            self.fake_parsed_host(ip=ip),
            self.fake_parsed_rubout(ip=ip),
            self.fake_parsed_host(ip=ip, mac=new_owner),
            ]
        self.assertEqual({ip: new_owner}, gather_hosts(hosts))

    def test_is_lease_and_is_host_recognize_lease(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        [parsed_lease] = lease_parser.searchString(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
            }
            """ % params))
        self.assertEqual(
            (True, False),
            (is_lease(parsed_lease), is_host(parsed_lease)))

    def test_is_lease_and_is_host_recognize_host(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        [parsed_host] = lease_parser.searchString(dedent("""\
            host %(ip)s {
                hardware ethernet %(mac)s;
            }
            """ % params))
        self.assertEqual(
            (False, True),
            (is_lease(parsed_host), is_host(parsed_host)))

    def test_get_host_mac_returns_None_for_host(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        [parsed_host] = lease_parser.searchString(dedent("""\
            host %(ip)s {
                hardware ethernet %(mac)s;
            }
            """ % params))
        self.assertEqual(params['mac'], get_host_mac(parsed_host))

    def test_get_host_mac_returns_None_for_rubout(self):
        ip = factory.getRandomIPAddress()
        [parsed_host] = lease_parser.searchString(dedent("""\
            host %s {
                deleted;
            }
            """ % ip))
        self.assertIsNone(get_host_mac(parsed_host))

    def test_get_host_mac_returns_None_for_rubout_even_with_mac(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        [parsed_host] = lease_parser.searchString(dedent("""\
            host %(ip)s {
                deleted;
                hardware ethernet %(mac)s;
            }
            """ % params))
        self.assertIsNone(get_host_mac(parsed_host))

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
                rewind binding state free;
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

    def test_parse_leases_parses_host(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            host %(ip)s {
                dynamic;
                hardware ethernet %(mac)s;
                fixed-address %(ip)s;
            }
            """ % params))
        self.assertEqual({params['ip']: params['mac']}, leases)

    def test_parse_leases_parses_host_rubout(self):
        leases = parse_leases(dedent("""\
            host %s {
                deleted;
            }
            """ % factory.getRandomIPAddress()))
        self.assertEqual({}, leases)

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

    def test_parse_leases_recognizes_host_deleted_statement_as_rubout(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            host %(ip)s {
                dynamic;
                hardware ethernet %(mac)s;
                fixed-address %(ip)s;
                deleted;
            }
            """ % params))
        self.assertEqual({}, leases)

    def test_host_declaration_is_like_an_unexpired_lease(self):
        params = {
            'ip': factory.getRandomIPAddress(),
            'mac': factory.getRandomMACAddress(),
        }
        leases = parse_leases(dedent("""\
            host %(ip)s {
                hardware ethernet %(mac)s;
                fixed-address %(ip)s;
            }
            """ % params))
        self.assertEqual({params['ip']: params['mac']}, leases)

    def test_combine_entries_accepts_host_followed_by_expired_lease(self):
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            self.fake_parsed_host(ip=ip, mac=mac),
            self.fake_parsed_lease(ip=ip, ends=earlier),
            ]
        self.assertEqual({ip: mac}, combine_entries(entries))

    def test_combine_entries_accepts_expired_lease_followed_by_host(self):
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            self.fake_parsed_lease(ip=ip, ends=earlier),
            self.fake_parsed_host(ip=ip, mac=mac),
            ]
        self.assertEqual({ip: mac}, combine_entries(entries))

    def test_combine_entries_accepts_rubout_followed_by_current_lease(self):
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        entries = [
            self.fake_parsed_host(ip=ip),
            self.fake_parsed_rubout(ip=ip),
            self.fake_parsed_lease(ip=ip, mac=mac),
            ]
        self.assertEqual({ip: mac}, combine_entries(entries))

    def test_combine_entries_ignores_rubout_followed_by_expired_lease(self):
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            self.fake_parsed_host(ip=ip),
            self.fake_parsed_rubout(ip=ip),
            self.fake_parsed_lease(ip=ip, mac=mac, ends=earlier),
            ]
        self.assertEqual({}, combine_entries(entries))

    def test_combine_entries_ignores_expired_lease_followed_by_rubout(self):
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            self.fake_parsed_host(ip=ip),
            self.fake_parsed_lease(ip=ip, mac=mac, ends=earlier),
            self.fake_parsed_rubout(ip=ip),
            ]
        self.assertEqual({}, combine_entries(entries))

    def test_combine_entries_accepts_valid_lease_followed_by_rubout(self):
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        entries = [
            self.fake_parsed_host(ip=ip),
            self.fake_parsed_lease(ip=ip, mac=mac),
            self.fake_parsed_rubout(ip=ip),
            ]
        self.assertEqual({ip: mac}, combine_entries(entries))

    def test_combine_entries_accepts_reassigned_host(self):
        ip = factory.getRandomIPAddress()
        mac = factory.getRandomMACAddress()
        entries = [
            self.fake_parsed_host(ip=ip),
            self.fake_parsed_rubout(ip=ip),
            self.fake_parsed_host(ip=ip, mac=mac),
            ]
        self.assertEqual({ip: mac}, combine_entries(entries))

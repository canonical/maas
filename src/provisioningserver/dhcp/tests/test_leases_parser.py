# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
from netaddr import IPAddress
from provisioningserver.dhcp import (
    leases_parser,
    leases_parser_fast,
)
from provisioningserver.dhcp.leases_parser import (
    combine_entries,
    gather_hosts,
    gather_leases,
    get_expiry_date,
    get_host_ip,
    get_host_mac,
    has_expired,
    is_host,
    is_lease,
    lease_parser,
)


class Lease(object):

    def __init__(self, lease_or_host, host, fixed_address, hardware, ends):
        self.lease_or_host = lease_or_host
        self.host = host
        self.hardware = hardware
        setattr(self, 'fixed-address', fixed_address)
        self.ends = ends

    def __iter__(self):
        return iter(self.__dict__.keys())


def fake_parsed_lease(ip=None, mac=None, ends=None,
                      entry_type='lease'):
    """Fake a lease as produced by the parser."""
    if ip is None:
        ip = factory.make_ipv4_address()
    if mac is None:
        mac = factory.make_mac_address()
    Hardware = namedtuple('Hardware', ['mac'])
    lease = Lease(entry_type, ip, ip, Hardware(mac), ends)
    return lease


def fake_parsed_host(ip=None, mac=None):
    """Fake a host declaration as produced by the parser."""
    return fake_parsed_lease(mac=mac, ip=ip, entry_type='host')


class Rubout(object):

    def __init__(self, lease_or_host, host):
        self.lease_or_host = lease_or_host
        self.host = host
        self.deleted = 'true'

    def __iter__(self):
        return iter(self.__dict__.keys())


def get_fake_parsed_rubouts(ip=None, mac=None):
    """Returns 2 rubouts, one for the given IP and one for the given MAC.

    Rubouts now come in pairs: one with the IP as the key to cope with
    old-style host map declarations and one with the MAC as the key to deal
    with recent host map declarations.
    """
    if ip is None:
        ip = factory.make_ipv4_address()
    if mac is None:
        mac = factory.make_mac_address()
    return [
        fake_parsed_rubout(key=ip),
        fake_parsed_rubout(key=mac),
    ]


def fake_parsed_rubout(key=None):
    """Fake a "rubout" host declaration."""
    if key is None:
        key = factory.make_ipv4_address()
    rubout = Rubout('host', key)
    return rubout


class TestLeasesParsers(MAASTestCase):

    scenarios = (
        ("original", dict(parse=leases_parser.parse_leases)),
        ("fast", dict(parse=leases_parser_fast.parse_leases)),
    )

    sample_lease_entry = dedent("""\
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
        """)

    sample_host_entry = dedent("""\
       host %(mac)s {
           dynamic;
           hardware ethernet %(mac)s;
           fixed-address%(six)s %(ip)s;
       }
        """)

    def make_host_entry(self, ip, mac=None):
        """Create a host entry with the given IP and MAC addresses.

        The host entry will be in IPv4 or IPv6 depending on `ip`.
        """
        if mac is None:
            mac = factory.make_mac_address()
        params = {
            'ip': unicode(ip),
            'mac': mac,
            }
        # The "six" parameter is suffixed to the fixed-address keyword:
        # empty string for IPv4, or "6" for IPv6.
        if IPAddress(ip).version == 6:
            params['six'] = '6'
        else:
            params['six'] = ''
        return self.sample_host_entry % params

    def make_lease_entry(self, ip, mac):
        """Create a lease entry mapping an IP address to a MAC address."""
        params = {
            'ip': unicode(ip),
            'mac': mac,
            }
        return self.sample_lease_entry % params

    def test_parse_leases_copes_with_empty_file(self):
        self.assertEqual([], self.parse(""))

    def test_parse_leases_parses_IPv4_lease(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        leases = self.parse(self.make_lease_entry(ip, mac))
        self.assertEqual([(ip, mac)], leases)

    def test_parse_leases_parses_IPv6_lease(self):
        ip = unicode(factory.make_ipv6_address())
        mac = factory.make_mac_address()
        leases = self.parse(self.make_lease_entry(ip, mac))
        self.assertEqual([(ip, mac)], leases)

    def test_parse_leases_parses_IPv4_host(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        lease = self.make_host_entry(ip, mac)
        leases = self.parse(lease)
        self.assertEqual([(ip, mac)], leases)

    def test_parse_leases_parses_IPv6_host(self):
        ip = factory.make_ipv6_address()
        mac = factory.make_mac_address()
        leases = self.parse(self.make_host_entry(ip, mac))
        self.assertEqual([(unicode(ip), mac)], leases)

    def test_parse_leases_parses_full_sized_IPv6_address(self):
        ip = 'fc00:0001:0000:0000:0000:0000:0000:0000'
        leases = self.parse(self.make_host_entry(ip))
        self.assertEqual([ip], [ipx for ipx, mac in leases])

    def test_parse_leases_copes_with_misleading_values(self):
        params = {
            'ip1': factory.make_ipv4_address(),
            'mac1': factory.make_mac_address(),
            'ip2': factory.make_ipv4_address(),
            'mac2': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            host %(mac1)s {
                dynamic;
              ### NOTE the following value has a closing brace, and
              ### also looks like a host record.
                uid "foo}host 12.34.56.78 { }";
                hardware ethernet %(mac1)s;
                fixed-address %(ip1)s;
            }
              ### NOTE the extra indent on the line below.
                host %(mac2)s {
                dynamic;
                hardware ethernet %(mac2)s;
                fixed-address %(ip2)s;
            }
            """ % params))
        self.assertEqual(
            [(params['ip1'], params['mac1']),
             (params['ip2'], params['mac2'])],
            leases)

    def test_parse_leases_parses_host_rubout(self):
        leases = self.parse(dedent("""\
            host %s {
                deleted;
            }
            """ % factory.make_mac_address()))
        self.assertEqual([], leases)

    def test_parse_leases_ignores_incomplete_lease_at_end(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
            'incomplete_ip': factory.make_ipv4_address(),
        }
        leases = self.parse(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
            }
            lease %(incomplete_ip)s {
                starts 5 2010/01/01 00:00:05;
            """ % params))
        self.assertEqual([(params['ip'], params['mac'])], leases)

    def test_parse_leases_ignores_comments(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            # Top comment (ignored).
            lease %(ip)s { # End-of-line comment (ignored).
                # Comment in lease block (ignored).
                hardware ethernet %(mac)s;  # EOL comment in lease (ignored).
            } # Comment right after closing brace (ignored).
            # End comment (ignored).
            """ % params))
        self.assertEqual([(params['ip'], params['mac'])], leases)

    def test_parse_leases_ignores_expired_leases(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
                ends 1 2001/01/01 00:00:00;
            }
            """ % params))
        self.assertEqual([], leases)

    def test_parse_leases_treats_never_as_eternity(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
                ends never;
            }
            """ % params))
        self.assertEqual([(params['ip'], params['mac'])], leases)

    def test_parse_leases_treats_missing_end_date_as_eternity(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            lease %(ip)s {
                hardware ethernet %(mac)s;
            }
            """ % params))
        self.assertEqual([(params['ip'], params['mac'])], leases)

    def test_parse_leases_takes_all_leases_for_address(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'old_owner': factory.make_mac_address(),
            'new_owner': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            lease %(ip)s {
                hardware ethernet %(old_owner)s;
            }
            lease %(ip)s {
                hardware ethernet %(new_owner)s;
            }
            """ % params))
        self.assertEqual(
            [(params['ip'], params['old_owner']),
             (params['ip'], params['new_owner'])],
            leases)

    def test_parse_leases_recognizes_host_deleted_statement_as_rubout(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            host %(ip)s {
                dynamic;
                hardware ethernet %(mac)s;
                fixed-address %(ip)s;
                deleted;
            }
            """ % params))
        self.assertEqual([], leases)

    def test_host_declaration_is_like_an_unexpired_lease(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        leases = self.parse(dedent("""\
            host %(ip)s {
                hardware ethernet %(mac)s;
                fixed-address %(ip)s;
            }
            """ % params))
        self.assertEqual([(params['ip'], params['mac'])], leases)


class TestLeasesParserFast(MAASTestCase):

    def test_expired_lease_does_not_shadow_earlier_host_stanza(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac1': factory.make_mac_address(),
            'mac2': factory.make_mac_address(),
        }
        leases = leases_parser_fast.parse_leases(dedent("""\
            host %(mac1)s {
                dynamic;
                hardware ethernet %(mac1)s;
                fixed-address %(ip)s;
            }
            lease %(ip)s {
                starts 5 2010/01/01 00:00:01;
                ends 1 2010/01/01 00:00:02;
                hardware ethernet %(mac2)s;
            }
            """ % params))
        # The lease has expired so it doesn't shadow the host stanza,
        # and so the MAC returned is from the host stanza.
        self.assertEqual([(params["ip"], params["mac1"])], leases)

    def test_active_lease_shadows_earlier_host_stanza(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac1': factory.make_mac_address(),
            'mac2': factory.make_mac_address(),
        }
        leases = leases_parser_fast.parse_leases(dedent("""\
            host %(mac1)s {
                dynamic;
                hardware ethernet %(mac1)s;
                fixed-address %(ip)s;
            }
            lease %(ip)s {
                starts 5 2010/01/01 00:00:01;
                hardware ethernet %(mac2)s;
            }
            """ % params))
        # The lease hasn't expired, so shadows the earlier host stanza.
        self.assertEqual(
            [(params["ip"], params["mac1"]), (params["ip"], params["mac2"])],
            leases)

    def test_host_stanza_shadows_earlier_active_lease(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac1': factory.make_mac_address(),
            'mac2': factory.make_mac_address(),
        }
        leases = leases_parser_fast.parse_leases(dedent("""\
            lease %(ip)s {
                starts 5 2010/01/01 00:00:01;
                hardware ethernet %(mac2)s;
            }
            host %(ip)s {
                dynamic;
                hardware ethernet %(mac1)s;
                fixed-address %(ip)s;
            }
            """ % params))
        # The lease hasn't expired, but the host entry is later, so it
        # shadows the earlier lease stanza.
        self.assertEqual(
            [(params["ip"], params["mac2"]), (params["ip"], params["mac1"])],
            leases)


class TestLeasesParserFunctions(MAASTestCase):

    def test_get_expiry_date_parses_expiry_date(self):
        lease = fake_parsed_lease(ends='0 2011/01/02 03:04:05')
        self.assertEqual(
            datetime(
                year=2011, month=01, day=02,
                hour=03, minute=04, second=05),
            get_expiry_date(lease))

    def test_get_expiry_date_returns_None_for_never(self):
        self.assertIsNone(
            get_expiry_date(fake_parsed_lease(ends='never')))

    def test_get_expiry_date_returns_None_if_no_expiry_given(self):
        self.assertIsNone(get_expiry_date(fake_parsed_lease(ends=None)))

    def test_has_expired_returns_False_for_eternal_lease(self):
        now = datetime.utcnow()
        self.assertFalse(has_expired(fake_parsed_lease(ends=None), now))

    def test_has_expired_returns_False_for_future_expiry_date(self):
        now = datetime.utcnow()
        later = '1 2035/12/31 23:59:59'
        self.assertFalse(has_expired(fake_parsed_lease(ends=later), now))

    def test_has_expired_returns_True_for_past_expiry_date(self):
        now = datetime.utcnow()
        earlier = '1 2001/01/01 00:00:00'
        self.assertTrue(
            has_expired(fake_parsed_lease(ends=earlier), now))

    def test_gather_leases_finds_current_leases(self):
        lease = fake_parsed_lease()
        self.assertEqual(
            [(getattr(lease, 'fixed-address'), lease.hardware.mac)],
            gather_leases([lease]))

    def test_gather_leases_ignores_expired_leases(self):
        earlier = '1 2001/01/01 00:00:00'
        lease = fake_parsed_lease(ends=earlier)
        self.assertEqual([], gather_leases([lease]))

    def test_gather_leases_combines_expired_and_current_leases(self):
        earlier = '1 2001/01/01 00:00:00'
        ip = factory.make_ipv4_address()
        old_owner = factory.make_mac_address()
        new_owner = factory.make_mac_address()
        leases = [
            fake_parsed_lease(ip=ip, mac=old_owner, ends=earlier),
            fake_parsed_lease(ip=ip, mac=new_owner),
            ]
        self.assertEqual([(ip, new_owner)], gather_leases(leases))

    def test_gather_leases_ignores_ordering(self):
        earlier = '1 2001/01/01 00:00:00'
        ip = factory.make_ipv4_address()
        old_owner = factory.make_mac_address()
        new_owner = factory.make_mac_address()
        leases = [
            fake_parsed_lease(ip=ip, mac=new_owner),
            fake_parsed_lease(ip=ip, mac=old_owner, ends=earlier),
            ]
        self.assertEqual([(ip, new_owner)], gather_leases(leases))

    def test_gather_leases_ignores_host_declarations(self):
        self.assertEqual([], gather_leases([fake_parsed_host()]))

    def test_gather_hosts_finds_hosts(self):
        host = fake_parsed_host()
        self.assertEqual(
            [(getattr(host, 'fixed-address'), host.hardware.mac)],
            gather_hosts([host]))

    def test_gather_hosts_ignores_unaccompanied_rubouts(self):
        self.assertEqual([], gather_hosts([fake_parsed_rubout()]))

    def test_gather_hosts_ignores_rubbed_out_entries(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        hosts = [
            fake_parsed_host(ip=ip, mac=mac)
            ] + get_fake_parsed_rubouts(ip=ip, mac=mac)
        self.assertEqual([], gather_hosts(hosts))

    def test_gather_hosts_follows_reassigned_host(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        new_owner = factory.make_mac_address()
        hosts = [
            fake_parsed_host(ip=ip, mac=mac)
        ] + get_fake_parsed_rubouts(ip=ip, mac=mac) + [
            fake_parsed_host(ip=ip, mac=new_owner)
        ]
        self.assertEqual([(ip, new_owner)], gather_hosts(hosts))

    def test_is_lease_and_is_host_recognize_lease(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
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
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
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
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        [parsed_host] = lease_parser.searchString(dedent("""\
            host %(ip)s {
                hardware ethernet %(mac)s;
            }
            """ % params))
        self.assertEqual(params['mac'], get_host_mac(parsed_host))

    def test_get_host_mac_returns_mac_for_rubout(self):
        mac = factory.make_mac_address()
        [parsed_host] = lease_parser.searchString(dedent("""\
            host %s {
                deleted;
            }
            """ % mac))
        self.assertEqual(mac, get_host_mac(parsed_host))

    def test_get_host_ip_returns_None_for_rubout(self):
        params = {
            'ip': factory.make_ipv4_address(),
            'mac': factory.make_mac_address(),
        }
        [parsed_host] = lease_parser.searchString(dedent("""\
            host %(mac)s {
                deleted;
            }
            """ % params))
        self.assertIsNone(get_host_ip(parsed_host))

    def test_combine_entries_accepts_host_followed_by_expired_lease(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            fake_parsed_host(ip=ip, mac=mac),
            fake_parsed_lease(ip=ip, ends=earlier),
            ]
        self.assertEqual([(ip, mac)], combine_entries(entries))

    def test_combine_entries_accepts_expired_lease_followed_by_host(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            fake_parsed_lease(ip=ip, ends=earlier),
            fake_parsed_host(ip=ip, mac=mac),
            ]
        self.assertEqual([(ip, mac)], combine_entries(entries))

    def test_combine_entries_accepts_old_rubout_followed_by_lease(self):
        ip = factory.make_ipv4_address()
        old_mac = factory.make_mac_address()
        mac = factory.make_mac_address()
        entries = [
            fake_parsed_host(ip=ip, mac=old_mac),
            # Create old-style individual IP-based rubout.
            fake_parsed_rubout(key=ip),
            fake_parsed_lease(ip=ip, mac=mac),
            ]
        self.assertEqual([(ip, mac)], combine_entries(entries))

    def test_combine_entries_accepts_rubout_followed_by_current_lease(self):
        ip = factory.make_ipv4_address()
        old_mac = factory.make_mac_address()
        mac = factory.make_mac_address()
        entries = [
            fake_parsed_host(ip=ip, mac=old_mac)
        ] + get_fake_parsed_rubouts(ip=ip, mac=mac) + [
            fake_parsed_lease(ip=ip, mac=mac),
        ]
        self.assertEqual([(ip, mac)], combine_entries(entries))

    def test_combine_entries_ignores_rubout_followed_by_expired_lease(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            fake_parsed_host(ip=ip, mac=mac)
        ] + get_fake_parsed_rubouts(ip=ip, mac=mac) + [
            fake_parsed_lease(ip=ip, mac=mac, ends=earlier),
        ]
        self.assertEqual([], combine_entries(entries))

    def test_combine_entries_ignores_expired_lease_followed_by_rubout(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        earlier = '1 2001/01/01 00:00:00'
        entries = [
            fake_parsed_host(ip=ip, mac=mac),
            fake_parsed_lease(ip=ip, mac=mac, ends=earlier)
        ] + get_fake_parsed_rubouts(ip=ip, mac=mac)
        self.assertEqual([], combine_entries(entries))

    def test_combine_entries_accepts_valid_lease_followed_by_rubout(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        entries = [
            fake_parsed_host(ip=ip, mac=mac),
            fake_parsed_lease(ip=ip, mac=mac),
        ] + get_fake_parsed_rubouts(ip=ip, mac=mac)
        self.assertEqual([(ip, mac)], combine_entries(entries))

    def test_combine_entries_accepts_reassigned_host(self):
        ip = factory.make_ipv4_address()
        mac = factory.make_mac_address()
        old_mac = factory.make_mac_address()
        entries = [
            fake_parsed_host(ip=ip, mac=old_mac)
        ] + get_fake_parsed_rubouts(ip=ip, mac=mac) + [
            fake_parsed_host(ip=ip, mac=mac),
        ]
        self.assertEqual([(ip, mac)], combine_entries(entries))

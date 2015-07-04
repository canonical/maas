# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test ISC configuration file parser/generator."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = []


from textwrap import dedent

from maasserver.utils.isc import (
    make_isc_string,
    parse_isc_string,
)
from maastesting.testcase import MAASTestCase


class TestParseISCString(MAASTestCase):

    def test_parses_simple_bind_options(self):
        testdata = dedent("""\
            options {
                directory "/var/cache/bind";

                dnssec-validation auto;

                auth-nxdomain no;    # conform to RFC1035
                listen-on-v6 { any; };
            };
            """)
        options = parse_isc_string(testdata)
        self.assertEqual(
            {u'options': {u'auth-nxdomain': u'no',
                          u'directory': u'"/var/cache/bind"',
                          u'dnssec-validation': u'auto',
                          u'listen-on-v6': {u'any': True}}}, options)

    def test_parses_bind_acl(self):
        testdata = dedent("""\
            acl goodclients {
                192.0.2.0/24;
                localhost;
                localnets;
            };
            """)
        acl = parse_isc_string(testdata)
        self.assertEqual(
            {u'acl goodclients': {u'192.0.2.0/24': True,
                                  u'localhost': True,
                                  u'localnets': True}}, acl)

    def test_parses_multiple_forwarders(self):
        testdata = dedent("""\
            forwarders {
                91.189.94.2;
                91.189.94.3;
                91.189.94.4;
                91.189.94.5;
                91.189.94.6;
            };
            """)
        forwarders = parse_isc_string(testdata)
        self.assertEqual(
            {u'forwarders': {u'91.189.94.2': True,
                             u'91.189.94.3': True,
                             u'91.189.94.4': True,
                             u'91.189.94.5': True,
                             u'91.189.94.6': True}}, forwarders)

    def test_parses_bug_1413388_config(self):
        testdata = dedent("""\
            acl canonical-int-ns { 91.189.90.151; 91.189.89.192;  };

            options {
                directory "/var/cache/bind";

                forwarders {
                    91.189.94.2;
                    91.189.94.2;
                };

                dnssec-validation auto;

                auth-nxdomain no;    # conform to RFC1035
                listen-on-v6 { any; };

                allow-query { any; };
                allow-transfer { 10.222.64.1; canonical-int-ns; };

                notify explicit;
                also-notify { 91.189.90.151; 91.189.89.192;  };

                allow-query-cache { 10.222.64.0/18; };
                recursion yes;
            };

            zone "."  { type master; file "/etc/bind/db.special"; };
            """)
        config = parse_isc_string(testdata)
        self.assertEqual(
            {u'acl canonical-int-ns':
             {u'91.189.89.192': True, u'91.189.90.151': True},
             u'options': {u'allow-query': {u'any': True},
                          u'allow-query-cache': {u'10.222.64.0/18': True},
                          u'allow-transfer': {u'10.222.64.1': True,
                                              u'canonical-int-ns': True},
                          u'also-notify': {u'91.189.89.192': True,
                                           u'91.189.90.151': True},
                          u'auth-nxdomain': u'no',
                          u'directory': u'"/var/cache/bind"',
                          u'dnssec-validation': u'auto',
                          u'forwarders': {u'91.189.94.2': True},
                          u'listen-on-v6': {u'any': True},
                          u'notify': u'explicit',
                          u'recursion': u'yes'},
             u'zone "."':
             {u'file': u'"/etc/bind/db.special"', u'type': u'master'}},
            config)

    def test_parse_then_make_then_parse_generates_identical_config(self):
        testdata = dedent("""\
            acl canonical-int-ns { 91.189.90.151; 91.189.89.192;  };

            options {
                directory "/var/cache/bind";

                forwarders {
                    91.189.94.2;
                    91.189.94.2;
                };

                dnssec-validation auto;

                auth-nxdomain no;    # conform to RFC1035
                listen-on-v6 { any; };

                allow-query { any; };
                allow-transfer { 10.222.64.1; canonical-int-ns; };

                notify explicit;
                also-notify { 91.189.90.151; 91.189.89.192;  };

                allow-query-cache { 10.222.64.0/18; };
                recursion yes;
            };

            zone "."  { type master; file "/etc/bind/db.special"; };
            """)
        config = parse_isc_string(testdata)
        config_string = make_isc_string(config)
        config = parse_isc_string(config_string)
        self.assertEqual(
            {u'acl canonical-int-ns':
             {u'91.189.89.192': True, u'91.189.90.151': True},
             u'options': {u'allow-query': {u'any': True},
                          u'allow-query-cache': {u'10.222.64.0/18': True},
                          u'allow-transfer': {u'10.222.64.1': True,
                                              u'canonical-int-ns': True},
                          u'also-notify': {u'91.189.89.192': True,
                                           u'91.189.90.151': True},
                          u'auth-nxdomain': u'no',
                          u'directory': u'"/var/cache/bind"',
                          u'dnssec-validation': u'auto',
                          u'forwarders': {u'91.189.94.2': True},
                          u'listen-on-v6': {u'any': True},
                          u'notify': u'explicit',
                          u'recursion': u'yes'},
             u'zone "."':
             {u'file': u'"/etc/bind/db.special"', u'type': u'master'}},
            config)

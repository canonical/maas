# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test ISC configuration file parser/generator."""

from collections import OrderedDict
from textwrap import dedent

from maastesting.testcase import MAASTestCase
from provisioningserver.utils.isc import (
    ISCParseException,
    make_isc_string,
    parse_isc_string,
    read_isc_file,
)


class TestParseISCString(MAASTestCase):
    def test_parses_simple_bind_options(self):
        testdata = dedent(
            """\
            options {
                directory "/var/cache/bind";

                dnssec-validation auto;

                auth-nxdomain no;    # conform to RFC1035
                listen-on-v6 { any; };
            };
            """
        )
        options = parse_isc_string(testdata)
        self.assertEqual(
            OrderedDict(
                [
                    (
                        "options",
                        OrderedDict(
                            [
                                ("directory", '"/var/cache/bind"'),
                                ("dnssec-validation", "auto"),
                                ("auth-nxdomain", "no"),
                                ("listen-on-v6", OrderedDict([("any", True)])),
                            ]
                        ),
                    )
                ]
            ),
            options,
        )

    def test_parses_bind_acl(self):
        testdata = dedent(
            """\
            acl goodclients {
                192.0.2.0/24;
                localhost;
                localnets;
            };
            """
        )
        acl = parse_isc_string(testdata)
        self.assertEqual(
            {
                "acl goodclients": {
                    "192.0.2.0/24": True,
                    "localhost": True,
                    "localnets": True,
                }
            },
            acl,
        )

    def test_parses_multiple_forwarders(self):
        testdata = dedent(
            """\
            forwarders {
                91.189.94.2;
                91.189.94.3;
                91.189.94.4;
                91.189.94.5;
                91.189.94.6;
            };
            """
        )
        forwarders = parse_isc_string(testdata)
        self.assertEqual(
            {
                "forwarders": {
                    "91.189.94.2": True,
                    "91.189.94.3": True,
                    "91.189.94.4": True,
                    "91.189.94.5": True,
                    "91.189.94.6": True,
                }
            },
            forwarders,
        )

    def test_parses_bug_1413388_config(self):
        testdata = dedent(
            """\
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
            """
        )
        config = parse_isc_string(testdata)
        self.assertEqual(
            {
                "acl canonical-int-ns": {
                    "91.189.89.192": True,
                    "91.189.90.151": True,
                },
                "options": {
                    "allow-query": {"any": True},
                    "allow-query-cache": {"10.222.64.0/18": True},
                    "allow-transfer": {
                        "10.222.64.1": True,
                        "canonical-int-ns": True,
                    },
                    "also-notify": {
                        "91.189.89.192": True,
                        "91.189.90.151": True,
                    },
                    "auth-nxdomain": "no",
                    "directory": '"/var/cache/bind"',
                    "dnssec-validation": "auto",
                    "forwarders": {"91.189.94.2": True},
                    "listen-on-v6": {"any": True},
                    "notify": "explicit",
                    "recursion": "yes",
                },
                'zone "."': {
                    "file": '"/etc/bind/db.special"',
                    "type": "master",
                },
            },
            config,
        )

    def test_parse_then_make_then_parse_generates_identical_config(self):
        testdata = dedent(
            """\
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
            """
        )
        config = parse_isc_string(testdata)
        config_string = make_isc_string(config)
        config = parse_isc_string(config_string)
        self.assertEqual(
            OrderedDict(
                [
                    (
                        "acl canonical-int-ns",
                        OrderedDict(
                            [("91.189.90.151", True), ("91.189.89.192", True)]
                        ),
                    ),
                    (
                        "options",
                        OrderedDict(
                            [
                                ("directory", '"/var/cache/bind"'),
                                (
                                    "forwarders",
                                    OrderedDict([("91.189.94.2", True)]),
                                ),
                                ("dnssec-validation", "auto"),
                                ("auth-nxdomain", "no"),
                                ("listen-on-v6", OrderedDict([("any", True)])),
                                ("allow-query", OrderedDict([("any", True)])),
                                (
                                    "allow-transfer",
                                    OrderedDict(
                                        [
                                            ("10.222.64.1", True),
                                            ("canonical-int-ns", True),
                                        ]
                                    ),
                                ),
                                ("notify", "explicit"),
                                (
                                    "also-notify",
                                    OrderedDict(
                                        [
                                            ("91.189.90.151", True),
                                            ("91.189.89.192", True),
                                        ]
                                    ),
                                ),
                                (
                                    "allow-query-cache",
                                    OrderedDict([("10.222.64.0/18", True)]),
                                ),
                                ("recursion", "yes"),
                            ]
                        ),
                    ),
                    (
                        'zone "."',
                        OrderedDict(
                            [
                                ("type", "master"),
                                ("file", '"/etc/bind/db.special"'),
                            ]
                        ),
                    ),
                ]
            ),
            config,
        )

    def test_parser_preserves_order(self):
        testdata = dedent(
            """\
            forwarders {
                9.9.9.9;
                8.8.8.8;
                7.7.7.7;
                6.6.6.6;
                5.5.5.5;
                4.4.4.4;
                3.3.3.3;
                2.2.2.2;
                1.1.1.1;
            };
            """
        )
        forwarders = parse_isc_string(testdata)
        self.assertEqual(
            OrderedDict(
                [
                    (
                        "forwarders",
                        OrderedDict(
                            [
                                ("9.9.9.9", True),
                                ("8.8.8.8", True),
                                ("7.7.7.7", True),
                                ("6.6.6.6", True),
                                ("5.5.5.5", True),
                                ("4.4.4.4", True),
                                ("3.3.3.3", True),
                                ("2.2.2.2", True),
                                ("1.1.1.1", True),
                            ]
                        ),
                    )
                ]
            ),
            forwarders,
        )

    def test_parse_unmatched_brackets_throws_iscparseexception(self):
        with self.assertRaisesRegex(
            ISCParseException, r"^Invalid brackets\.$"
        ):
            parse_isc_string("forwarders {")

    def test_parse_malformed_list_throws_iscparseexception(self):
        with self.assertRaisesRegex(ISCParseException, "^Syntax error$"):
            parse_isc_string("forwarders {{}a;;b}")

    def test_parse_forgotten_semicolons_throw_iscparseexception(self):
        with self.assertRaisesRegex(ISCParseException, r"^Invalid brackets\."):
            parse_isc_string("a { b; } { c; } d e;")

    def test_read_isc_file(self):
        testdata = dedent(
            """\
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
            """
        )
        testfile = self.make_file(contents=testdata)
        parsed = read_isc_file(testfile)
        self.assertEqual(
            {
                "acl canonical-int-ns": {
                    "91.189.89.192": True,
                    "91.189.90.151": True,
                },
                "options": {
                    "allow-query": {"any": True},
                    "allow-query-cache": {"10.222.64.0/18": True},
                    "allow-transfer": {
                        "10.222.64.1": True,
                        "canonical-int-ns": True,
                    },
                    "also-notify": {
                        "91.189.89.192": True,
                        "91.189.90.151": True,
                    },
                    "auth-nxdomain": "no",
                    "directory": '"/var/cache/bind"',
                    "dnssec-validation": "auto",
                    "forwarders": {"91.189.94.2": True},
                    "listen-on-v6": {"any": True},
                    "notify": "explicit",
                    "recursion": "yes",
                },
                'zone "."': {
                    "file": '"/etc/bind/db.special"',
                    "type": "master",
                },
            },
            parsed,
        )

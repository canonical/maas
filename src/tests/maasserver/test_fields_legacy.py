# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Gap-free tests for `maasserver.fields`, split out of the legacy
`src/maasserver/tests/test_fields.py`: the legacy `TestXMLField`,
`TestLargeObjectField`, `TestCIDRField` and `TestIPv4CIDRField` classes stay
there in the region-legacy pytest leg, while these classes run in the
main pytest suite."""

from random import choice
import re

from django.core.exceptions import ValidationError

from maasserver.fields import (
    HostListFormField,
    IPListFormField,
    IPPortListFormField,
    IPWithOptionalPort,
    MODEL_NAME_VALIDATOR,
    NodeChoiceField,
    SubnetListFormField,
    SystemdIntervalField,
    URLOrPPAFormField,
    URLOrPPAValidator,
    VersionedTextFileField,
)
from maasserver.models import Node, VersionedTextFile
from maasserver.models.interface import Interface
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.testcase import MAASTestCase


class TestModelNameValidator(MAASServerTestCase):
    def test_valid_name(self):
        self.assertIsNone(MODEL_NAME_VALIDATOR("a-valid-name"))

    def test_valid_with_number(self):
        self.assertIsNone(MODEL_NAME_VALIDATOR("with-number-10"))

    def test_valid_with_spaces(self):
        self.assertIsNone(MODEL_NAME_VALIDATOR("with spaces"))

    def test_invalid_start_space(self):
        self.assertRaises(
            ValidationError, MODEL_NAME_VALIDATOR, " not-at-start"
        )

    def test_invalid_start_dash(self):
        self.assertRaises(
            ValidationError, MODEL_NAME_VALIDATOR, "-not-at-start"
        )


class TestIPListFormField(MAASTestCase):
    def test_accepts_none(self):
        self.assertIsNone(IPListFormField().clean(None))

    def test_accepts_single_ip(self):
        ip = factory.make_ip_address()
        self.assertEqual(ip, IPListFormField().clean(ip))

    def test_accepts_space_separated_ips(self):
        ips = [factory.make_ip_address() for _ in range(5)]
        input = " ".join(ips)
        self.assertEqual(input, IPListFormField().clean(input))

    def test_accepts_comma_separated_ips(self):
        ips = [factory.make_ip_address() for _ in range(5)]
        input = ",".join(ips)
        self.assertEqual(" ".join(ips), IPListFormField().clean(input))

    def test_rejects_invalid_input(self):
        invalid = factory.make_name("invalid")
        input = " ".join([factory.make_ip_address(), invalid])
        error = self.assertRaises(
            ValidationError, IPListFormField().clean, input
        )
        self.assertIn("Invalid IP address: %s" % invalid, error.message)

    def test_separators_dont_conflict_with_ipv4_address(self):
        self.assertIsNone(
            re.search(IPListFormField.separators, factory.make_ipv4_address())
        )

    def test_separators_dont_conflict_with_ipv6_address(self):
        self.assertIsNone(
            re.search(IPListFormField.separators, factory.make_ipv6_address())
        )


class TestIPPortListFormField(MAASTestCase):
    def test_accepts_ipv4_with_port(self):
        ips = [factory.make_ip_address(ipv6=False) for _ in range(5)]
        ip_ports = [f"{ip}:80" for ip in ips]
        input = ",".join(ip_ports)
        self.assertEqual(
            [(ip, 80) for ip in ips], IPPortListFormField().clean(input)
        )

    def test_accepts_ipv4_without_port(self):
        ips = [factory.make_ip_address(ipv6=False) for _ in range(5)]
        input = ",".join(ips)
        self.assertEqual(
            [(ip, 80) for ip in ips],
            IPPortListFormField(default_port=80).clean(input),
        )

    def test_accepts_ipv6_with_port(self):
        ips = [factory.make_ip_address(ipv6=True) for _ in range(5)]
        ip_ports = [f"[{ip}]:80" for ip in ips]
        input = ",".join(ip_ports)
        self.assertEqual(
            [(ip, 80) for ip in ips], IPPortListFormField().clean(input)
        )

    def test_accepts_ipv6_without_port(self):
        ips = [factory.make_ip_address(ipv6=True) for _ in range(5)]
        input = ",".join(ips)
        self.assertEqual(
            [(ip, 80) for ip in ips],
            IPPortListFormField(default_port=80).clean(input),
        )

    def test_rejects_invalid_ip(self):
        ip_ports = [
            f"{factory.make_ip_address(ipv6=False)}:80" for _ in range(4)
        ]
        invalid = f"{factory.make_name()}:80"
        ip_ports.append(invalid)
        input = ",".join(ip_ports)
        error = self.assertRaises(
            ValidationError, IPPortListFormField().clean, input
        )
        self.assertIn(
            f"Invalid IP and port combination: {invalid}", error.message
        )


class TestHostListFormField(MAASTestCase):
    def test_accepts_none(self):
        self.assertIsNone(HostListFormField().clean(None))

    def test_accepts_single_ip(self):
        ip = factory.make_ip_address()
        self.assertEqual(ip, HostListFormField().clean(ip))

    def test_accepts_space_separated_ips(self):
        ips = [factory.make_ip_address() for _ in range(5)]
        input = " ".join(ips)
        self.assertEqual(input, HostListFormField().clean(input))

    def test_accepts_comma_separated_ips(self):
        ips = [factory.make_ip_address() for _ in range(5)]
        input = ",".join(ips)
        self.assertEqual(" ".join(ips), HostListFormField().clean(input))

    def test_accepts_hostname(self):
        hostname = factory.make_hostname()
        self.assertEqual(hostname, HostListFormField().clean(hostname))

    def test_accepts_space_separated_hostnames(self):
        hostnames = factory.make_hostname(), factory.make_hostname()
        input = " ".join(hostnames)
        self.assertEqual(input, HostListFormField().clean(input))

    def test_accepts_comma_separated_hostnames(self):
        hostnames = factory.make_hostname(), factory.make_hostname()
        input = ",".join(hostnames)
        self.assertEqual(" ".join(hostnames), HostListFormField().clean(input))

    def test_accepts_misc(self):
        servers = {
            "::1",
            "1::",
            "1::2",
            "1:2::3",
            "1::2:3",
            "1:2::3:4",
            "::127.0.0.1",
        }
        input = ",".join(servers)
        self.assertEqual(" ".join(servers), HostListFormField().clean(input))

    def test_rejects_invalid_ipv4_address(self):
        input = "%s 12.34.56.999" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, HostListFormField().clean, input
        )
        self.assertEqual(
            "Failed to detect a valid IP address from '12.34.56.999'.",
            error.message,
        )

    def test_rejects_invalid_ipv6_address(self):
        input = "%s fe80::abcde" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, HostListFormField().clean, input
        )
        self.assertEqual(
            "Failed to detect a valid IP address from 'fe80::abcde'.",
            error.message,
        )

    def test_rejects_invalid_hostname(self):
        input = "%s abc-.foo" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, HostListFormField().clean, input
        )
        self.assertEqual(
            error.message,
            "Invalid hostname: Label cannot start or end with hyphen: 'abc-'.",
        )


class TestNodeChoiceField(MAASServerTestCase):
    def test_allows_selecting_by_system_id(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_Node()
        node_field = NodeChoiceField(Node.objects.filter())
        self.assertEqual(node, node_field.clean(node.system_id))

    def test_allows_selecting_by_hostname(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_Node()
        node_field = NodeChoiceField(Node.objects.filter())
        self.assertEqual(node, node_field.clean(node.hostname))

    def test_raises_exception_when_not_found(self):
        for _ in range(3):
            factory.make_Node()
        node_field = NodeChoiceField(Node.objects.filter())
        self.assertRaises(
            ValidationError, node_field.clean, factory.make_name("query")
        )

    def test_works_with_multiple_entries_in_queryset(self):
        # Regression test for lp:1551399
        vlan = factory.make_VLAN()
        node = factory.make_Node_with_Interface_on_Subnet(vlan=vlan)
        factory.make_Interface(node=node, vlan=vlan)
        qs = Node.objects.filter_by_vids([vlan.vid])
        node_field = NodeChoiceField(qs)
        # Double check that we have duplicated entires
        self.assertEqual(2, len(qs.filter(system_id=node.system_id)))
        self.assertEqual(node, node_field.clean(node.system_id))


class TestSubnetListFormField(MAASTestCase):
    def test_accepts_none(self):
        self.assertIsNone(SubnetListFormField().clean(None))

    def test_accepts_single_ip(self):
        ip = factory.make_ip_address()
        self.assertEqual(ip, SubnetListFormField().clean(ip))

    def test_accepts_space_separated_ips(self):
        ips = [factory.make_ip_address() for _ in range(5)]
        input = " ".join(ips)
        self.assertEqual(input, SubnetListFormField().clean(input))

    def test_accepts_comma_separated_ips(self):
        ips = [factory.make_ip_address() for _ in range(5)]
        input = ",".join(ips)
        self.assertEqual(" ".join(ips), SubnetListFormField().clean(input))

    def test_accepts_single_subnet(self):
        subnet = str(factory.make_ipv4_network())
        self.assertEqual(subnet, SubnetListFormField().clean(subnet))

    def test_accepts_space_separated_subnets(self):
        subnets = [str(factory.make_ipv6_network()) for _ in range(5)]
        input = " ".join(subnets)
        self.assertEqual(input, SubnetListFormField().clean(input))

    def test_accepts_comma_separated_subnets(self):
        subnets = [str(factory.make_ipv4_network()) for _ in range(5)]
        input = ",".join(subnets)
        self.assertEqual(" ".join(subnets), SubnetListFormField().clean(input))

    def test_accepts_hostname(self):
        hostname = factory.make_hostname()
        self.assertEqual(hostname, SubnetListFormField().clean(hostname))

    def test_accepts_space_separated_hostnames(self):
        hostnames = factory.make_hostname(), factory.make_hostname()
        input = " ".join(hostnames)
        self.assertEqual(input, SubnetListFormField().clean(input))

    def test_accepts_comma_separated_hostnames(self):
        hostnames = factory.make_hostname(), factory.make_hostname()
        input = ",".join(hostnames)
        self.assertEqual(
            " ".join(hostnames), SubnetListFormField().clean(input)
        )

    def test_accepts_misc(self):
        servers = {
            "::1",
            "1::",
            "1::2",
            "1:2::3",
            "1::2:3",
            "1:2::3:4",
            "::127.0.0.1",
        }
        input = ",".join(servers)
        self.assertEqual(" ".join(servers), SubnetListFormField().clean(input))

    def test_rejects_invalid_ipv4_address(self):
        input = "%s 12.34.56.999" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, SubnetListFormField().clean, input
        )
        self.assertEqual("Invalid IP address: 12.34.56.999.", error.message)

    def test_rejects_invalid_ipv6_address(self):
        input = "%s fe80::abcde" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, SubnetListFormField().clean, input
        )
        self.assertEqual("Invalid IP address: fe80::abcde.", error.message)

    def test_rejects_invalid_ipv4_subnet(self):
        input = "%s 10.10.10.300/24" % factory.make_ipv4_network()
        error = self.assertRaises(
            ValidationError, SubnetListFormField().clean, input
        )
        self.assertEqual("Invalid network: 10.10.10.300/24.", error.message)

    def test_rejects_invalid_ipv6_subnet(self):
        input = "%s 100::/300" % factory.make_ipv6_network()
        error = self.assertRaises(
            ValidationError, SubnetListFormField().clean, input
        )
        self.assertEqual("Invalid network: 100::/300.", error.message)

    def test_rejects_invalid_hostname(self):
        input = "%s abc-.foo" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, SubnetListFormField().clean, input
        )
        self.assertEqual(
            error.message,
            "Invalid hostname: Label cannot start or end with hyphen: 'abc-'.",
        )


class TestVersionedTextFileField(MAASServerTestCase):
    def test_creates_new(self):
        data = factory.make_string()
        versioned_text_file_field = VersionedTextFileField()
        versioned_text_file = versioned_text_file_field.clean(data)
        self.assertEqual(data, versioned_text_file.data)
        self.assertIsNone(versioned_text_file.previous_version)

    def test_create_requires_value(self):
        versioned_text_file_field = VersionedTextFileField()
        self.assertRaises(
            ValidationError, versioned_text_file_field.clean, None
        )

    def test_create_new_accepts_dict_with_comment(self):
        data = factory.make_string()
        comment = factory.make_name("comment")
        versioned_text_file_field = VersionedTextFileField()
        versioned_text_file = versioned_text_file_field.clean(
            {"data": data, "comment": comment}
        )
        self.assertEqual(data, versioned_text_file.data)
        self.assertEqual(comment, versioned_text_file.comment)
        self.assertIsNone(versioned_text_file.previous_version)

    def test_update_does_nothing_on_none(self):
        data = VersionedTextFile.objects.create(data=factory.make_string())
        versioned_text_file_field = VersionedTextFileField(initial=data)
        self.assertEqual(data, versioned_text_file_field.clean(None))

    def test_creates_new_link(self):
        old_ver = VersionedTextFile.objects.create(data=factory.make_string())
        versioned_text_file_field = VersionedTextFileField(initial=old_ver)
        data = factory.make_string()
        new_ver = versioned_text_file_field.clean(data)
        self.assertEqual(data, new_ver.data)
        self.assertEqual(old_ver, new_ver.previous_version)

    def test_creates_new_link_accepts_dict(self):
        old_ver = VersionedTextFile.objects.create(data=factory.make_string())
        versioned_text_file_field = VersionedTextFileField(initial=old_ver)
        data = factory.make_string()
        comment = factory.make_name("comment")
        new_ver = versioned_text_file_field.clean(
            {"new_data": data, "comment": comment}
        )
        self.assertEqual(data, new_ver.data)
        self.assertEqual(comment, new_ver.comment)
        self.assertEqual(old_ver, new_ver.previous_version)


class TestURLOrPPAValidator(MAASServerTestCase):
    def test_URLOrPPAValidator_validates_URL(self):
        validator = URLOrPPAValidator()
        self.assertIsNone(validator(factory.make_url(scheme="http")))
        self.assertIsNone(validator(factory.make_url(scheme="https")))

    def test_URLOrPPAValidator_catches_bad_url(self):
        validator = URLOrPPAValidator()
        bad_url = factory.make_name("bad_url")
        error = self.assertRaises(ValidationError, validator, bad_url)
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.message,
        )

    def test_URLOrPPAValidator_catches_bad_scheme(self):
        validator = URLOrPPAValidator()
        bad_url = factory.make_url(scheme="bad_scheme")
        error = self.assertRaises(ValidationError, validator, bad_url)
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.message,
        )

    def test_URLOrPPAValidator_validates_PPA(self):
        validator = URLOrPPAValidator()
        good_ppa = "ppa:{}/{}".format(
            factory.make_hostname(),
            factory.make_hostname(),
        )
        self.assertIsNone(validator(good_ppa))

    def test_URLOrPPAValidator_catches_bad_PPA_format(self):
        validator = URLOrPPAValidator()
        bad_ppa = "ppa:%s" % factory.make_hostname()
        error = self.assertRaises(ValidationError, validator, bad_ppa)
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.message,
        )

    def test_URLOrPPAValidator_catches_bad_PPA_hostname(self):
        validator = URLOrPPAValidator()
        bad_ppa = "ppa:{}/-{}".format(
            factory.make_hostname(),
            factory.make_hostname(),
        )
        error = self.assertRaises(ValidationError, validator, bad_ppa)
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.message,
        )


class TestURLOrPPAFormField(MAASServerTestCase):
    def test_rejects_none(self):
        error = self.assertRaises(
            ValidationError, URLOrPPAFormField().clean, None
        )
        self.assertEqual("This field is required.", error.message)

    def test_URLOrPPAFormField_validates_URL(self):
        url = factory.make_url(scheme="http")
        self.assertEqual(url, URLOrPPAFormField().clean(url))

    def test_URLOrPPAFormField_catches_bad_url(self):
        bad_url = factory.make_name("bad_url")
        error = self.assertRaises(
            ValidationError, URLOrPPAFormField().clean, bad_url
        )
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.messages[0],
        )

    def test_URLOrPPAFormField_catches_bad_scheme(self):
        bad_url = factory.make_url(scheme="bad_scheme")
        error = self.assertRaises(
            ValidationError, URLOrPPAFormField().clean, bad_url
        )
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.messages[0],
        )

    def test_URLOrPPAFormField_validates_PPA(self):
        url = f"ppa:{factory.make_hostname()}/{factory.make_hostname()}"
        self.assertEqual(url, URLOrPPAFormField().clean(url))

    def test_URLOrPPAFormField_catches_bad_PPA_format(self):
        bad_url = "ppa:%s" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, URLOrPPAFormField().clean, bad_url
        )
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.messages[0],
        )

    def test_URLOrPPAFormField_catches_bad_PPA_hostname(self):
        bad_url = "ppa:{}/-{}".format(
            factory.make_hostname(),
            factory.make_hostname(),
        )
        error = self.assertRaises(
            ValidationError, URLOrPPAFormField().clean, bad_url
        )
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.messages[0],
        )


class TestURLOrPPAField(MAASServerTestCase):
    def test_create_package_repository_ppa(self):
        # PackageRepository contains a URLOrPPAField. Make one with PPA.
        ppa_url = "ppa:{}/{}".format(
            factory.make_hostname(),
            factory.make_hostname(),
        )
        factory.make_PackageRepository(url=ppa_url)

    def test_create_package_repository_url(self):
        # PackageRepository contains a URLOrPPAField. Make one with URL.
        url = factory.make_url(scheme="http")
        factory.make_PackageRepository(url=url)

    def test_cannot_create_package_repository_bad_url(self):
        # PackageRepository contains a URLOrPPAField. Make one with bad URL.
        bad_url = factory.make_name("bad_url")
        error = self.assertRaises(
            ValidationError, factory.make_PackageRepository, url=bad_url
        )
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.messages[0],
        )

    def test_cannot_create_package_repository_bad_ppa(self):
        # PackageRepository contains a URLOrPPAField. Make one with bad PPA.
        bad_url = "ppa:%s" % factory.make_hostname()
        error = self.assertRaises(
            ValidationError, factory.make_PackageRepository, url=bad_url
        )
        self.assertEqual(
            "Enter a valid repository URL or PPA location.",
            error.messages[0],
        )


class TestSystemdIntervalField(MAASServerTestCase):
    def test_valid_interval(self):
        intervals = [
            "h",
            "hr",
            "hour",
            "hours",
            "m",
            "min",
            "minute",
            "minutes",
            "s",
            "sec",
            "second",
            "seconds",
        ]
        interval = choice(intervals)
        value = f"1{interval}"
        field = SystemdIntervalField()
        self.assertEqual(value, field.clean(value))

    def test_invalid_interval(self):
        value = "1 year"
        field = SystemdIntervalField()
        self.assertRaises(ValidationError, field.clean, value)


class TestIPWithOptionalPort(MAASTestCase):
    def test_accepts_ipv4(self):
        ip = factory.make_ip_address(ipv6=False)
        self.assertEqual(ip, IPWithOptionalPort().clean(ip))

    def test_accepts_ipv6(self):
        ips = [
            "::1",
            "ff06::c3",
            "0:0:0:0:0:ffff:192.1.56.10",
            "::ffff:12.12.12.12",
            factory.make_ip_address(ipv6=True),
        ]
        for ip in ips:
            self.assertEqual(ip, IPWithOptionalPort().clean(ip))

    def test_accepts_ipv4_with_port(self):
        ip = factory.make_ip_address(ipv6=False)
        ip_port = f"{ip}:5000"
        self.assertEqual(ip_port, IPWithOptionalPort().clean(ip_port))

    def test_accepts_ipv6_with_port(self):
        ips = [
            "::1",
            "ff06::c3",
            "0:0:0:0:0:ffff:192.1.56.10",
            "::ffff:12.12.12.12",
            factory.make_ip_address(ipv6=True),
        ]
        for ip in ips:
            # test ipv6 with and without square brackets
            ip_port = f"{ip}:5000"
            self.assertEqual(ip_port, IPWithOptionalPort().clean(ip_port))
            ip_port = f"[{ip}]:5000"
            self.assertEqual(ip_port, IPWithOptionalPort().clean(ip_port))

    def test_rejects_invalid_ipv4_address(self):
        ip = "12.34.56.999"
        error = self.assertRaises(
            ValidationError, IPWithOptionalPort().clean, ip
        )
        self.assertEqual(
            "Invalid IPv4/IPv6 address with optional port.", error.message
        )

    def test_rejects_invalid_ipv6_address(self):
        ips = ["fe80::abcde", "fe800:0:0:0:abcdfe:0"]
        for ip in ips:
            error = self.assertRaises(
                ValidationError, IPWithOptionalPort().clean, ip
            )
            self.assertEqual(
                "Invalid IPv4/IPv6 address with optional port.", error.message
            )

    def test_rejects_invalid_port(self):
        ip = "12.34.56.78"
        ports = [-1, 65536, 99999]
        for port in ports:
            error = self.assertRaises(
                ValidationError, IPWithOptionalPort().clean, f"{ip}:{port}"
            )
            self.assertEqual(
                "Invalid IPv4/IPv6 address with optional port.", error.message
            )


class TestMACAddressFieldLookups(MAASServerTestCase):
    """Format-agnostic ``startswith``/``contains`` lookups on mac_address."""

    def make_interface(self, mac_address):
        return factory.make_Interface(mac_address=mac_address)

    def test_startswith_ignores_separator_and_case(self):
        interface = self.make_interface("00:16:3e:55:60:96")
        for term in ("00:16:3E", "00-16-3e", "00163E", "0016.3e55"):
            self.assertEqual(
                [interface],
                list(Interface.objects.filter(mac_address__startswith=term)),
                term,
            )

    def test_startswith_does_not_match_other_prefix(self):
        self.make_interface("00:16:3e:55:60:96")
        self.assertEqual(
            [],
            list(Interface.objects.filter(mac_address__startswith="aa:bb")),
        )

    def test_contains_ignores_separator_and_case(self):
        interface = self.make_interface("00:16:3e:55:60:96")
        for term in ("3E:55", "3e-55", "3e55"):
            self.assertEqual(
                [interface],
                list(Interface.objects.filter(mac_address__contains=term)),
                term,
            )

    def test_contains_does_not_match_absent_fragment(self):
        self.make_interface("00:16:3e:55:60:96")
        self.assertEqual(
            [],
            list(Interface.objects.filter(mac_address__contains="ffff")),
        )

    def test_icontains_behaves_like_contains(self):
        interface = self.make_interface("00:16:3e:55:60:96")
        self.assertEqual(
            [interface],
            list(Interface.objects.filter(mac_address__icontains="3E-55")),
        )

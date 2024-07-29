# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from random import choice, randint
import re

from django.core.exceptions import ValidationError
from django.db import connection, DatabaseError
from psycopg2 import OperationalError

from maasserver.fields import (
    HostListFormField,
    IPListFormField,
    IPPortListFormField,
    LargeObjectField,
    LargeObjectFile,
    LXDAddressField,
    MODEL_NAME_VALIDATOR,
    NodeChoiceField,
    SubnetListFormField,
    SystemdIntervalField,
    URLOrPPAFormField,
    URLOrPPAValidator,
    VersionedTextFileField,
    VirshAddressField,
)
from maasserver.models import Node, VersionedTextFile
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASLegacyServerTestCase,
    MAASServerTestCase,
)
from maasserver.tests.models import (
    CIDRTestModel,
    IPv4CIDRTestModel,
    LargeObjectFieldModel,
    XMLFieldModel,
)
from maasserver.utils.orm import reload_object
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


class TestXMLField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

    def test_loads_string(self):
        name = factory.make_string()
        value = "<test/>"
        XMLFieldModel.objects.create(name=name, value=value)
        instance = XMLFieldModel.objects.get(name=name)
        self.assertEqual(value, instance.value)

    def test_lookup_xpath_exists_result(self):
        name = factory.make_string()
        XMLFieldModel.objects.create(name=name, value="<test/>")
        result = XMLFieldModel.objects.raw(
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//test"]
        )
        self.assertEqual(name, result[0].name)

    def test_lookup_xpath_exists_no_result(self):
        name = factory.make_string()
        XMLFieldModel.objects.create(name=name, value="<test/>")
        result = XMLFieldModel.objects.raw(
            "SELECT * FROM docs WHERE xpath_exists(%s, value)", ["//miss"]
        )
        self.assertEqual([], list(result))

    def test_save_non_wellformed_rejected(self):
        self.assertRaises(
            DatabaseError, XMLFieldModel.objects.create, value="<bad>"
        )

    def test_lookup_none(self):
        XMLFieldModel.objects.create(value=None)
        test_instance = XMLFieldModel.objects.get(value__isnull=True)
        self.assertIsNone(test_instance.value)


class TestLargeObjectField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

    def test_stores_data(self):
        data = factory.make_bytes()
        test_name = factory.make_name("name")
        test_instance = LargeObjectFieldModel(name=test_name)
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            stream.write(data)
        test_instance.large_object = large_object
        test_instance.save()
        test_instance = LargeObjectFieldModel.objects.get(name=test_name)
        with test_instance.large_object.open("rb") as stream:
            saved_data = stream.read()
        self.assertEqual(data, saved_data)

    def test_insists_on_binary_mode(self):
        message = "Large objects must be opened in binary mode."
        with self.assertRaisesRegex(ValueError, message):
            large_object = LargeObjectFile()
            large_object.open("w")

    def test_with_exit_calls_close(self):
        data = factory.make_bytes()
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            self.addCleanup(large_object.close)
            mock_close = self.patch(large_object, "close")
            stream.write(data)
        mock_close.assert_called_once_with()

    def test_unlink(self):
        data = factory.make_bytes()
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            stream.write(data)
        oid = large_object.oid
        large_object.unlink()
        self.assertEqual(0, large_object.oid)
        self.assertRaises(OperationalError, connection.connection.lobject, oid)

    def test_interates_on_block_size(self):
        # String size is multiple of block_size in the testing model
        data = factory.make_bytes(10 * 2)
        test_name = factory.make_name("name")
        test_instance = LargeObjectFieldModel(name=test_name)
        large_object = LargeObjectFile()
        with large_object.open("wb") as stream:
            stream.write(data)
        test_instance.large_object = large_object
        test_instance.save()
        test_instance = LargeObjectFieldModel.objects.get(name=test_name)
        with test_instance.large_object.open("rb") as stream:
            offset = 0
            for block in stream:
                self.assertEqual(data[offset : offset + 10], block)
                offset += 10

    def test_get_db_prep_value_returns_None_when_value_None(self):
        field = LargeObjectField()
        self.assertIsNone(field.get_db_prep_value(None))

    def test_get_db_prep_value_returns_oid_when_value_LargeObjectFile(self):
        oid = randint(1, 100)
        field = LargeObjectField()
        obj_file = LargeObjectFile()
        obj_file.oid = oid
        self.assertEqual(oid, field.get_db_prep_value(obj_file))

    def test_get_db_prep_value_raises_error_when_oid_less_than_zero(self):
        oid = randint(-100, 0)
        field = LargeObjectField()
        obj_file = LargeObjectFile()
        obj_file.oid = oid
        self.assertRaises(AssertionError, field.get_db_prep_value, obj_file)

    def test_get_db_prep_value_raises_error_when_not_LargeObjectFile(self):
        field = LargeObjectField()
        self.assertRaises(
            AssertionError, field.get_db_prep_value, factory.make_string()
        )

    def test_to_python_returns_None_when_value_None(self):
        field = LargeObjectField()
        self.assertIsNone(field.to_python(None))

    def test_to_python_returns_value_when_value_LargeObjectFile(self):
        field = LargeObjectField()
        obj_file = LargeObjectFile()
        self.assertEqual(obj_file, field.to_python(obj_file))

    def test_to_python_returns_LargeObjectFile_when_value_int(self):
        oid = randint(1, 100)
        field = LargeObjectField()
        # South normally substitutes a FakeModel here, but with a baseline
        # schema, we can skip the migration that creates LargeObjectField.
        self.patch(field, "model")
        obj_file = field.to_python(oid)
        self.assertEqual(oid, obj_file.oid)

    def test_to_python_returns_LargeObjectFile_when_value_long(self):
        oid = int(randint(1, 100))
        field = LargeObjectField()
        # South normally substitutes a FakeModel here, but with a baseline
        # schema, we can skip the migration that creates LargeObjectField.
        self.patch(field, "model")
        obj_file = field.to_python(oid)
        self.assertEqual(oid, obj_file.oid)

    def test_to_python_raises_error_when_not_valid_type(self):
        field = LargeObjectField()
        self.assertRaises(
            AssertionError, field.to_python, factory.make_string()
        )


class TestCIDRField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

    def test_stores_cidr(self):
        cidr = "192.0.2.0/24"
        instance = CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(cidr, reload_object(instance).cidr)

    def test_validates_cidr(self):
        cidr = "invalid-cidr"
        error = self.assertRaises(
            ValidationError, CIDRTestModel.objects.create, cidr=cidr
        )
        self.assertEqual(["invalid IPNetwork %s" % cidr], error.messages)

    def test_stores_cidr_with_bit_set_in_host_part(self):
        cidr = "192.0.2.1/24"
        normalized_cidr = "192.0.2.0/24"
        instance = CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(normalized_cidr, reload_object(instance).cidr)


class TestIPv4CIDRField(MAASLegacyServerTestCase):
    apps = ["maasserver.tests"]

    def test_stores_cidr(self):
        cidr = "192.0.2.0/24"
        instance = IPv4CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(cidr, reload_object(instance).cidr)

    def test_validates_cidr(self):
        cidr = "invalid-cidr"
        error = self.assertRaises(
            ValidationError, IPv4CIDRTestModel.objects.create, cidr=cidr
        )
        self.assertEqual(["Invalid network: %s" % cidr], error.messages)

    def test_stores_cidr_with_bit_set_in_host_part(self):
        cidr = "192.0.2.1/24"
        normalized_cidr = "192.0.2.0/24"
        instance = IPv4CIDRTestModel.objects.create(cidr=cidr)
        self.assertEqual(normalized_cidr, reload_object(instance).cidr)

    def test_fails_to_store_ipv6_cidr(self):
        cidr = "2001:DB8::/32"
        error = self.assertRaises(
            ValidationError, IPv4CIDRTestModel.objects.create, cidr=cidr
        )
        self.assertEqual(
            ["2001:DB8::/32: Only IPv4 networks supported."], error.messages
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

    def test_separators_dont_conflict_with_ipv4_address(self):
        self.assertIsNone(
            re.search(
                HostListFormField.separators, factory.make_ipv4_address()
            )
        )

    def test_separators_dont_conflict_with_ipv6_address(self):
        self.assertIsNone(
            re.search(
                HostListFormField.separators, factory.make_ipv6_address()
            )
        )

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
            "Invalid hostname: Label cannot start or end with "
            "hyphen: 'abc-'.",
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

    def test_separators_dont_conflict_with_ipv4_address(self):
        self.assertIsNone(
            re.search(
                SubnetListFormField.separators, factory.make_ipv4_address()
            )
        )

    def test_separators_dont_conflict_with_ipv6_address(self):
        self.assertIsNone(
            re.search(
                SubnetListFormField.separators, factory.make_ipv6_address()
            )
        )

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
            "Invalid hostname: Label cannot start or end with "
            "hyphen: 'abc-'.",
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


class TestVirshAddressField(MAASTestCase):
    def test_accepts_ipv4(self):
        ip = factory.make_ip_address(ipv6=False)
        self.assertEqual(ip, VirshAddressField().clean(ip))

    def test_accepts_ipv6(self):
        ips = [
            "[::1]",
            "::1",
            "ff06::c3",
            "0:0:0:0:0:ffff:192.1.56.10",
            "::ffff:12.12.12.12",
            factory.make_ip_address(ipv6=True),
        ]
        for ip in ips:
            self.assertEqual(ip, VirshAddressField().clean(ip))

    def test_accepts_complete_uri(self):
        driver = ["xen", "qemu", "test"]
        transport = "ssh"
        user = factory.make_name()
        host = factory.make_hostname()
        port = "8080"
        path = {factory.make_name()}
        param = factory.make_name()
        for d in driver:
            uri = f"{d}+{transport}://{user}@{host}:{port}/{path}?{param}"
            self.assertEqual(uri, VirshAddressField().clean(uri))

    def test_rejects_invalid_ipv4_address(self):
        ip = "12.34.56.999"
        error = self.assertRaises(
            ValidationError, VirshAddressField().clean, ip
        )
        self.assertEqual("Enter a valid virsh address.", error.message)

    def test_rejects_invalid_ipv6_address(self):
        ips = ["fe80::abcde", "fe800:0:0:0:abcdfe:0"]
        for ip in ips:
            error = self.assertRaises(
                ValidationError, VirshAddressField().clean, ip
            )
            self.assertEqual("Enter a valid virsh address.", error.message)

    def test_rejects_invalid_transport(self):
        transport, hostname = factory.make_name(), factory.make_hostname()
        uri = f"{transport}://{hostname}"
        error = self.assertRaises(
            ValidationError, VirshAddressField().clean, uri
        )
        self.assertEqual("Enter a valid virsh address.", error.message)


class TestLXDAddressField(MAASTestCase):
    def test_accepts_ipv4(self):
        ip = factory.make_ip_address(ipv6=False)
        self.assertEqual(ip, LXDAddressField().clean(ip))

    def test_accepts_ipv6(self):
        ips = [
            "[::1]",
            "::1",
            "ff06::c3",
            "0:0:0:0:0:ffff:192.1.56.10",
            "::ffff:12.12.12.12",
            factory.make_ip_address(ipv6=True),
        ]
        for ip in ips:
            self.assertEqual(ip, LXDAddressField().clean(ip))

    def test_accepts_ipv4_with_port(self):
        ip = factory.make_ip_address(ipv6=False)
        ip_port = f"{ip}:8443"
        self.assertEqual(ip_port, LXDAddressField().clean(ip_port))

    def test_accepts_ipv6_with_port(self):
        ips = [
            "[::1]",
            "::1",
            "ff06::c3",
            "0:0:0:0:0:ffff:192.1.56.10",
            "::ffff:12.12.12.12",
            factory.make_ip_address(ipv6=True),
        ]
        for ip in ips:
            ip_port = f"{ip}:8443"
            self.assertEqual(ip_port, LXDAddressField().clean(ip_port))

    def test_accepts_http_https_uri(self):
        schemes = ["http", "https"]
        hostname = factory.make_hostname()
        port = 8443
        for scheme in schemes:
            uri = f"{scheme}://{hostname}:{port}"
            self.assertEqual(uri, LXDAddressField().clean(uri))

    def test_rejects_invalid_ipv4_address(self):
        ip = "12.34.56.999"
        error = self.assertRaises(ValidationError, LXDAddressField().clean, ip)
        self.assertEqual("Enter a valid LXD address.", error.message)

    def test_rejects_invalid_ipv6_address(self):
        ips = ["fe80::abcde", "fe800:0:0:0:abcdfe:0"]
        for ip in ips:
            error = self.assertRaises(
                ValidationError, LXDAddressField().clean, ip
            )
            self.assertEqual("Enter a valid LXD address.", error.message)

    def test_rejects_invalid_scheme(self):
        scheme = factory.make_name()
        host = factory.make_hostname()
        port = 8443
        uri = f"{scheme}://{host}:{port}"
        error = self.assertRaises(
            ValidationError, LXDAddressField().clean, uri
        )
        self.assertEqual("Enter a valid LXD address.", error.message)

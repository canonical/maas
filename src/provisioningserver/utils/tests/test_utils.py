# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `provisioningserver.utils`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json
import os
from random import randint
from textwrap import dedent

from apiclient.maas_client import MAASClient
from apiclient.testing.credentials import make_api_credentials
from fixtures import EnvironmentVariableFixture
from maastesting import root
from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    Mock,
    sentinel,
    )
import provisioningserver
from provisioningserver.testing.testcase import PservTestCase
import provisioningserver.utils
from provisioningserver.utils import (
    classify,
    compose_URL,
    create_node,
    escape_py_literal,
    filter_dict,
    locate_config,
    maas_custom_config_markers,
    parse_key_value_file,
    Safe,
    ShellTemplate,
    write_custom_config_section,
    )
from testtools.matchers import (
    DirExists,
    EndsWith,
    )


def get_branch_dir(*path):
    """Locate a file or directory relative to this branch."""
    return os.path.abspath(os.path.join(root, *path))


class TestLocateConfig(MAASTestCase):
    """Tests for `locate_config`."""

    def test_returns_branch_etc_maas(self):
        self.assertEqual(get_branch_dir('etc/maas'), locate_config())
        self.assertThat(locate_config(), DirExists())

    def test_defaults_to_global_etc_maas_if_variable_is_unset(self):
        self.useFixture(EnvironmentVariableFixture('MAAS_CONFIG_DIR', None))
        self.assertEqual('/etc/maas', locate_config())

    def test_defaults_to_global_etc_maas_if_variable_is_empty(self):
        self.useFixture(EnvironmentVariableFixture('MAAS_CONFIG_DIR', ''))
        self.assertEqual('/etc/maas', locate_config())

    def test_returns_absolute_path(self):
        self.useFixture(EnvironmentVariableFixture('MAAS_CONFIG_DIR', '.'))
        self.assertTrue(os.path.isabs(locate_config()))

    def test_locates_config_file(self):
        filename = factory.make_string()
        self.assertEqual(
            get_branch_dir('etc/maas/', filename),
            locate_config(filename))

    def test_locates_full_path(self):
        path = [factory.make_string() for counter in range(3)]
        self.assertEqual(
            get_branch_dir('etc/maas/', *path),
            locate_config(*path))

    def test_normalizes_path(self):
        self.assertEquals(
            get_branch_dir('etc/maas/bar/szot'),
            locate_config('foo/.././bar///szot'))


class TestFilterDict(MAASTestCase):
    """Tests for `filter_dict`."""

    def test_keeps_desired_keys(self):
        key = factory.make_name('key')
        value = factory.make_name('value')
        self.assertEqual({key: value}, filter_dict({key: value}, {key}))

    def test_ignores_undesired_keys(self):
        items = {factory.make_name('key'): factory.make_name('value')}
        self.assertEqual({}, filter_dict(items, {factory.make_name('other')}))

    def test_leaves_original_intact(self):
        desired_key = factory.make_name('key')
        original = {
            desired_key: factory.make_name('value'),
            factory.make_name('otherkey'): factory.make_name('othervalue'),
        }
        copy = original.copy()

        result = filter_dict(copy, {desired_key})

        self.assertEqual({desired_key: original[desired_key]}, result)
        self.assertEqual(original, copy)

    def test_ignores_values_from_second_dict(self):
        key = factory.make_name('key')
        items = {key: factory.make_name('value')}
        keys = {key: factory.make_name('othervalue')}

        self.assertEqual(items, filter_dict(items, keys))


class TestSafe(MAASTestCase):
    """Test `Safe`."""

    def test_value(self):
        something = object()
        safe = Safe(something)
        self.assertIs(something, safe.value)

    def test_repr(self):
        string = factory.make_string()
        safe = Safe(string)
        self.assertEqual("<Safe %r>" % string, repr(safe))


class WriteCustomConfigSectionTest(MAASTestCase):
    """Test `write_custom_config_section`."""

    def test_appends_custom_section_initially(self):
        original = factory.make_name('Original-text')
        custom_text = factory.make_name('Custom-text')
        header, footer = maas_custom_config_markers
        self.assertEqual(
            [original, header, custom_text, footer],
            write_custom_config_section(original, custom_text).splitlines())

    def test_custom_section_ends_with_newline(self):
        self.assertThat(write_custom_config_section("x", "y"), EndsWith('\n'))

    def test_replaces_custom_section_only(self):
        header, footer = maas_custom_config_markers
        original = [
            "Text before custom section.",
            header,
            "Old custom section.",
            footer,
            "Text after custom section.",
            ]
        expected = [
            "Text before custom section.",
            header,
            "New custom section.",
            footer,
            "Text after custom section.",
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_ignores_header_without_footer(self):
        # If the footer of the custom config section is not found,
        # write_custom_config_section will pretend that the header is not
        # there and append a new custom section.  This does mean that there
        # will be two headers and one footer; a subsequent rewrite will
        # replace everything from the first header to the footer.
        header, footer = maas_custom_config_markers
        original = [
            header,
            "Old custom section (probably).",
            ]
        expected = [
            header,
            "Old custom section (probably).",
            header,
            "New custom section.",
            footer,
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_ignores_second_header(self):
        # If there are two custom-config headers but only one footer,
        # write_custom_config_section will treat everything between the
        # first header and the footer as custom config section, which it
        # will overwrite.
        header, footer = maas_custom_config_markers
        original = [
            header,
            "Old custom section (probably).",
            header,
            "More custom section.",
            footer,
            ]
        expected = [
            header,
            "New custom section.",
            footer,
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_ignores_footer_before_header(self):
        # Custom-section footers before the custom-section header are
        # ignored.  You might see this if there was an older custom
        # config section whose header has been changed or deleted.
        header, footer = maas_custom_config_markers
        original = [
            footer,
            "Possible old custom section.",
            ]
        expected = [
            footer,
            "Possible old custom section.",
            header,
            "New custom section.",
            footer,
            ]
        self.assertEqual(
            expected,
            write_custom_config_section(
                '\n'.join(original), "New custom section.").splitlines())

    def test_preserves_indentation_in_original(self):
        indented_text = "   text."
        self.assertIn(
            indented_text,
            write_custom_config_section(indented_text, "Custom section."))

    def test_preserves_indentation_in_custom_section(self):
        indented_text = "   custom section."
        self.assertIn(
            indented_text,
            write_custom_config_section("Original.", indented_text))

    def test_produces_sensible_text(self):
        # The other tests mostly operate on lists of lines, because it
        # eliminates problems with line endings.  This test here
        # verifies that the actual text you get is sensible, preserves
        # newlines, and generally looks normal.
        header, footer = maas_custom_config_markers
        original = dedent("""\
            Top.


            More.
            %s
            Old custom section.
            %s
            End.

            """) % (header, footer)
        new_custom_section = dedent("""\
            New custom section.

            With blank lines.""")
        expected = dedent("""\
            Top.


            More.
            %s
            New custom section.

            With blank lines.
            %s
            End.

            """) % (header, footer)
        self.assertEqual(
            expected,
            write_custom_config_section(original, new_custom_section))


class ParseConfigTest(MAASTestCase):
    """Testing for `parse_key_value_file`."""

    def test_parse_key_value_file_parses_config_file(self):
        contents = """
            key1: value1
            key2  :  value2
            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1', 'key2': 'value2'},
            parse_key_value_file(file_name))

    def test_parse_key_value_copes_with_empty_lines(self):
        contents = """
            key1: value1

            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1'}, parse_key_value_file(file_name))

    def test_parse_key_value_file_parse_alternate_separator(self):
        contents = """
            key1= value1
            key2   =  value2
            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1', 'key2': 'value2'},
            parse_key_value_file(file_name, separator='='))

    def test_parse_key_value_additional_eparator(self):
        contents = """
            key1: value1:value11
            """
        file_name = self.make_file(contents=contents)
        self.assertEqual(
            {'key1': 'value1:value11'}, parse_key_value_file(file_name))


class TestShellTemplate(MAASTestCase):
    """Test `ShellTemplate`."""

    def test_substitute_escapes(self):
        # Substitutions are shell-escaped.
        template = ShellTemplate("{{a}}")
        expected = "'1 2 3'"
        observed = template.substitute(a="1 2 3")
        self.assertEqual(expected, observed)

    def test_substitute_does_not_escape_safe(self):
        # Substitutions will not be escaped if they're marked with `safe`.
        template = ShellTemplate("{{a|safe}}")
        expected = "$ ! ()"
        observed = template.substitute(a="$ ! ()")
        self.assertEqual(expected, observed)

    def test_substitute_does_not_escape_safe_objects(self):
        # Substitutions will not be escaped if they're `safe` objects.
        template = ShellTemplate("{{safe(a)}}")
        expected = "$ ! ()"
        observed = template.substitute(a="$ ! ()")
        self.assertEqual(expected, observed)


class TestClassify(MAASTestCase):

    def test_no_subjects(self):
        self.assertSequenceEqual(
            ([], []), classify(sentinel.func, []))

    def test_subjects(self):
        subjects = [("one", 1), ("two", 2), ("three", 3)]
        is_even = lambda subject: subject % 2 == 0
        self.assertSequenceEqual(
            (['two'], ['one', 'three']),
            classify(is_even, subjects))


class TestQuotePyLiteral(MAASTestCase):

    def test_uses_repr(self):
        string = factory.make_name('string')
        repr_mock = self.patch(provisioningserver.utils, 'repr')
        escape_py_literal(string)
        self.assertThat(repr_mock, MockCalledOnceWith(string))

    def test_decodes_ascii(self):
        string = factory.make_name('string')
        output = factory.make_name('output')
        repr_mock = self.patch(provisioningserver.utils, 'repr')
        ascii_value = Mock()
        ascii_value.decode = Mock(return_value=output)
        repr_mock.return_value = ascii_value
        value = escape_py_literal(string)
        self.assertThat(ascii_value.decode, MockCalledOnceWith('ascii'))
        self.assertEqual(value, output)


class TestCreateNode(PservTestCase):

    def test_passes_on_no_duplicate_macs(self):
        url = '/api/1.0/nodes/'
        uuid = 'node-' + factory.make_UUID()
        macs = [factory.getRandomMACAddress() for x in range(3)]
        arch = factory.make_name('architecture')
        power_type = factory.make_name('power_type')
        power_parameters = {
            'power_address': factory.getRandomIPAddress(),
            'power_user': factory.make_name('power_user'),
            'power_pass': factory.make_name('power_pass'),
            'power_control': None,
            'system_id': uuid
        }

        make_api_credentials()
        provisioningserver.auth.record_api_credentials(
            ':'.join(make_api_credentials()))
        self.set_maas_url()
        get = self.patch(MAASClient, 'get')
        post = self.patch(MAASClient, 'post')

        # Test for no duplicate macs
        get_data = []
        response = factory.make_response(
            httplib.OK, json.dumps(get_data),
            'application/json')
        get.return_value = response
        create_node(macs, arch, power_type, power_parameters)
        post_data = {
            'architecture': arch,
            'power_type': power_type,
            'power_parameters': json.dumps(power_parameters),
            'mac_addresses': macs,
            'autodetect_nodegroup': 'true'
        }
        self.assertThat(post, MockCalledOnceWith(url, 'new', **post_data))

    def test_errors_on_duplicate_macs(self):
        url = '/api/1.0/nodes/'
        uuid = 'node-' + factory.make_UUID()
        macs = [factory.getRandomMACAddress() for x in range(3)]
        arch = factory.make_name('architecture')
        power_type = factory.make_name('power_type')
        power_parameters = {
            'power_address': factory.getRandomIPAddress(),
            'power_user': factory.make_name('power_user'),
            'power_pass': factory.make_name('power_pass'),
            'power_control': None,
            'system_id': uuid
        }

        make_api_credentials()
        provisioningserver.auth.record_api_credentials(
            ':'.join(make_api_credentials()))
        self.set_maas_url()
        get = self.patch(MAASClient, 'get')
        post = self.patch(MAASClient, 'post')

        # Test for a duplicate mac
        resource_uri1 = url + "%s/macs/%s/" % (uuid, macs[0])
        get_data = [
            {
                "macaddress_set": [
                    {
                        "resource_uri": resource_uri1,
                        "mac_address": macs[0]
                    }
                ]
            }
        ]
        response = factory.make_response(
            httplib.OK, json.dumps(get_data),
            'application/json')
        get.return_value = response
        create_node(macs, arch, power_type, power_parameters)
        self.assertThat(post, MockNotCalled())


class TestComposeURL(MAASTestCase):

    def make_path(self):
        """Return an arbitrary URL path part."""
        return '%s/%s' % (factory.make_name('root'), factory.make_name('sub'))

    def make_network_interface(self):
        return 'eth%d' % randint(0, 100)

    def test__inserts_IPv4(self):
        ip = factory.getRandomIPAddress()
        path = self.make_path()
        self.assertEqual(
            'http://%s/%s' % (ip, path),
            compose_URL('http:///%s' % path, ip))

    def test__inserts_IPv6_with_brackets(self):
        ip = factory.make_ipv6_address()
        path = self.make_path()
        self.assertEqual(
            'http://[%s]/%s' % (ip, path),
            compose_URL('http:///%s' % path, ip))

    def test__escapes_IPv6_zone_index(self):
        ip = factory.make_ipv6_address()
        zone = self.make_network_interface()
        hostname = '%s%%%s' % (ip, zone)
        path = self.make_path()
        self.assertEqual(
            'http://[%s%%25%s]/%s' % (ip, zone, path),
            compose_URL('http:///%s' % path, hostname))

    def test__inserts_bracketed_IPv6_unchanged(self):
        ip = factory.make_ipv6_address()
        hostname = '[%s]' % ip
        path = self.make_path()
        self.assertEqual(
            'http://%s/%s' % (hostname, path),
            compose_URL('http:///%s' % path, hostname))

    def test__does_not_escape_bracketed_IPv6_zone_index(self):
        ip = factory.make_ipv6_address()
        zone = self.make_network_interface()
        path = self.make_path()
        hostname = '[%s%%25%s]' % (ip, zone)
        self.assertEqual(
            'http://%s/%s' % (hostname, path),
            compose_URL('http:///%s' % path, hostname))

    def test__inserts_hostname(self):
        hostname = factory.make_name('host')
        path = self.make_path()
        self.assertEqual(
            'http://%s/%s' % (hostname, path),
            compose_URL('http:///%s' % path, hostname))

    def test__preserves_query(self):
        ip = factory.getRandomIPAddress()
        key = factory.make_name('key')
        value = factory.make_name('value')
        self.assertEqual(
            'https://%s?%s=%s' % (ip, key, value),
            compose_URL('https://?%s=%s' % (key, value), ip))

    def test__preserves_port_with_IPv4(self):
        ip = factory.getRandomIPAddress()
        port = factory.pick_port()
        self.assertEqual(
            'https://%s:%s/' % (ip, port),
            compose_URL('https://:%s/' % port, ip))

    def test__preserves_port_with_IPv6(self):
        ip = factory.make_ipv6_address()
        port = factory.pick_port()
        self.assertEqual(
            'https://[%s]:%s/' % (ip, port),
            compose_URL('https://:%s/' % port, ip))

    def test__preserves_port_with_hostname(self):
        hostname = factory.make_name('host')
        port = factory.pick_port()
        self.assertEqual(
            'https://%s:%s/' % (hostname, port),
            compose_URL('https://:%s/' % port, hostname))

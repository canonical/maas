# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `MAAS_URL` configuration update code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from random import randint
from textwrap import dedent

from maastesting.factory import factory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
)
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    Mock,
)
from provisioningserver import configure_maas_url
from provisioningserver.configure_maas_url import substitute_pserv_yaml_line
from testtools.matchers import (
    FileContains,
    StartsWith,
)


class TestRewriteConfigFile(MAASTestCase):

    def test__rewrites_file(self):
        path = self.make_file(contents='foo\n')
        configure_maas_url.rewrite_config_file(path, lambda line: 'bar')
        self.assertThat(path, FileContains('bar\n'))

    def test__sets_access_permissions(self):
        writer = self.patch(configure_maas_url, 'atomic_write')
        mode = 0215
        path = self.make_file()
        configure_maas_url.rewrite_config_file(
            path, lambda line: line, mode=mode)
        self.assertThat(writer, MockCalledOnceWith(ANY, path, mode=mode))

    def test__preserves_trailing_newline(self):
        path = self.make_file(contents='x\n')
        configure_maas_url.rewrite_config_file(path, lambda line: line)
        self.assertThat(path, FileContains('x\n'))

    def test__ensures_trailing_newline(self):
        path = self.make_file(contents='x')
        configure_maas_url.rewrite_config_file(path, lambda line: line)
        self.assertThat(path, FileContains('x\n'))


class TestUpdateMAASClusterConf(MAASTestCase):

    def patch_file(self, content):
        """Inject a fake `/etc/maas/maas_cluster.conf`."""
        path = self.make_file(name='maas_cluster.conf', contents=content)
        self.patch(configure_maas_url, 'MAAS_CLUSTER_CONF', path)
        return path

    def test__updates_realistic_file(self):
        config_file = self.patch_file(dedent("""\
            # Leading comments.
            MAAS_URL="http://10.9.8.7/MAAS"
            CLUSTER_UUID="5d02950e-6318-8195-ac3e-e6ccb12673c5"
            """))
        configure_maas_url.update_maas_cluster_conf('http://1.2.3.4/MAAS')
        self.assertThat(
            config_file,
            FileContains(dedent("""\
                # Leading comments.
                MAAS_URL="http://1.2.3.4/MAAS"
                CLUSTER_UUID="5d02950e-6318-8195-ac3e-e6ccb12673c5"
                """)))

    def test__updates_quoted_value(self):
        old_url = factory.make_url()
        new_url = factory.make_url()
        config_file = self.patch_file('MAAS_URL="%s"\n' % old_url)
        configure_maas_url.update_maas_cluster_conf(new_url)
        self.assertThat(
            config_file,
            FileContains('MAAS_URL="%s"\n' % new_url))

    def test__updates_unquoted_value(self):
        old_url = factory.make_url()
        new_url = factory.make_url()
        config_file = self.patch_file('MAAS_URL=%s\n' % old_url)
        configure_maas_url.update_maas_cluster_conf(new_url)
        self.assertThat(
            config_file,
            FileContains('MAAS_URL="%s"\n' % new_url))

    def test__leaves_other_lines_unchanged(self):
        old_content = '#MAAS_URL="%s"\n' % factory.make_url()
        config_file = self.patch_file(old_content)
        configure_maas_url.update_maas_cluster_conf(factory.make_url())
        self.assertThat(config_file, FileContains(old_content))


class TestExtractHost(MAASTestCase):

    def test__extracts_hostname(self):
        host = factory.make_name('host').lower()
        port = factory.pick_port()
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://%s/path' % host))
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://%s:%d' % (host, port)))

    def test__extracts_IPv4_address(self):
        host = factory.make_ipv4_address()
        port = factory.pick_port()
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://%s' % host))
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://%s:%d' % (host, port)))

    def test__extracts_IPv6_address(self):
        host = factory.make_ipv6_address()
        port = factory.pick_port()
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://[%s]' % host))
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://[%s]:%d' % (host, port)))

    def test__extracts_IPv6_address_with_zone_index(self):
        host = (
            factory.make_ipv6_address() +
            '%25' +
            factory.make_name('zone').lower())
        port = factory.pick_port()
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://[%s]' % host))
        self.assertEqual(
            host,
            configure_maas_url.extract_host('http://[%s]:%d' % (host, port)))


class TestSubstitutePservYamlLine(MAASTestCase):

    def make_generator_line(self, url):
        return "  generator: %s" % url

    def test__replaces_hostname_generator_URL(self):
        old_host = factory.make_name('old-host')
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line('http://%s' % old_host)
        self.assertEqual(
            self.make_generator_line('http://%s' % new_host),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__replaces_IPv4_generator_URL(self):
        old_host = factory.make_ipv4_address()
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line('http://%s' % old_host)
        self.assertEqual(
            self.make_generator_line('http://%s' % new_host),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__replaces_IPv6_generator_URL(self):
        old_host = factory.make_ipv6_address()
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line('http://[%s]' % old_host)
        self.assertEqual(
            self.make_generator_line('http://%s' % new_host),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__replaces_IPv6_generator_URL_with_zone_index(self):
        old_host = (
            factory.make_ipv6_address() +
            '%25' +
            factory.make_name('zone')
            )
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line('http://[%s]' % old_host)
        self.assertEqual(
            self.make_generator_line('http://%s' % new_host),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__inserts_IPv6_with_brackets(self):
        old_host = factory.make_name('old-host')
        new_host = '[%s]' % factory.make_ipv6_address()
        input_line = self.make_generator_line('http://%s' % old_host)
        self.assertEqual(
            self.make_generator_line('http://%s' % new_host),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__inserts_IPv6_without_brackets(self):
        old_host = factory.make_name('old-host')
        new_host = factory.make_ipv6_address()
        input_line = self.make_generator_line('http://%s' % old_host)
        self.assertEqual(
            self.make_generator_line('http://[%s]' % new_host),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__preserves_port_after_simple_host(self):
        port = factory.pick_port()
        old_host = factory.make_name('old-host')
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line(
            'http://%s:%d' % (old_host, port))
        self.assertEqual(
            self.make_generator_line('http://%s:%d' % (new_host, port)),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__preserves_port_with_IPv6(self):
        port = factory.pick_port()
        old_host = factory.make_ipv6_address()
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line(
            'http://[%s]:%d' % (old_host, port))
        self.assertEqual(
            self.make_generator_line('http://%s:%d' % (new_host, port)),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__preserves_port_with_IPv6_and_zone_index(self):
        port = factory.pick_port()
        old_host = (
            factory.make_ipv6_address() +
            '%25' +
            factory.make_name('zone')
            )
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line(
            'http://[%s]:%d' % (old_host, port))
        self.assertEqual(
            self.make_generator_line('http://%s:%d' % (new_host, port)),
            substitute_pserv_yaml_line(new_host, input_line))

    def test__preserves_other_line(self):
        line = '#' + self.make_generator_line(factory.make_url())
        self.assertEqual(
            line,
            substitute_pserv_yaml_line(factory.make_name('host'), line))

    def test__preserves_indentation(self):
        spaces = ' ' * randint(0, 10)
        input_line = spaces + 'generator: %s' % factory.make_url()
        output_line = substitute_pserv_yaml_line(
            factory.make_name('host'), input_line)
        self.assertThat(output_line, StartsWith(spaces + 'generator:'))

    def test__preserves_trailing_comments(self):
        comment = " # Trailing comment."
        old_host = factory.make_name('old-host')
        new_host = factory.make_name('new-host')
        input_line = self.make_generator_line('http://%s' % old_host) + comment
        self.assertEqual(
            self.make_generator_line('http://%s' % new_host) + comment,
            substitute_pserv_yaml_line(new_host, input_line))


class TestUpdatePservYaml(MAASTestCase):

    def patch_file(self, content):
        """Inject a fake `/etc/maas/pserv.yaml`."""
        path = self.make_file(name='pserv.yaml', contents=content)
        self.patch(configure_maas_url, 'PSERV_YAML', path)
        return path

    def test__updates_realistic_file(self):
        old_host = factory.make_name('old-host')
        new_host = factory.make_name('new-host')
        config_file = self.patch_file(dedent("""\
            ## TFTP configuration.
            tftp:
              ## The URL to be contacted to generate PXE configurations.
              generator: http://%s/MAAS/api/1.0/pxeconfig/
            """) % old_host)
        configure_maas_url.update_pserv_yaml(new_host)
        self.assertThat(
            config_file,
            FileContains(dedent("""\
                ## TFTP configuration.
                tftp:
                  ## The URL to be contacted to generate PXE configurations.
                  generator: http://%s/MAAS/api/1.0/pxeconfig/
                """) % new_host))


class TestAddArguments(MAASTestCase):

    def test__accepts_maas_url(self):
        url = factory.make_url()
        parser = ArgumentParser()
        configure_maas_url.add_arguments(parser)
        args = parser.parse_args([url])
        self.assertEqual(url, args.maas_url)


class TestRun(MAASTestCase):

    def make_args(self, maas_url):
        args = Mock()
        args.maas_url = maas_url
        return args

    def patch_read_file(self):
        return self.patch(configure_maas_url, 'read_text_file')

    def patch_write_file(self):
        return self.patch(configure_maas_url, 'atomic_write')

    def test__updates_maas_cluster_conf(self):
        reader = self.patch_read_file()
        writer = self.patch_write_file()
        url = factory.make_url()
        configure_maas_url.run(self.make_args(url))
        self.assertThat(reader, MockAnyCall('/etc/maas/maas_cluster.conf'))
        self.assertThat(
            writer,
            MockAnyCall(ANY, '/etc/maas/maas_cluster.conf', mode=0640))

    def test__updates_pserv_yaml(self):
        reader = self.patch_read_file()
        writer = self.patch_write_file()
        url = factory.make_url()
        configure_maas_url.run(self.make_args(url))
        self.assertThat(reader, MockAnyCall('/etc/maas/pserv.yaml'))
        self.assertThat(
            writer,
            MockAnyCall(ANY, '/etc/maas/pserv.yaml', mode=0644))

    def test__passes_host_to_update_pserv_yaml(self):
        self.patch_read_file()
        self.patch_write_file()
        update_pserv_yaml = self.patch(configure_maas_url, 'update_pserv_yaml')
        host = factory.make_name('host').lower()
        url = factory.make_url(netloc=host)
        configure_maas_url.run(self.make_args(url))
        self.assertThat(update_pserv_yaml, MockCalledOnceWith(host))

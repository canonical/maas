# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `maasserver.preseed` and related bits and bobs."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import os
from pipes import quote
from urlparse import urlparse

from django.conf import settings
from django.core.urlresolvers import reverse
from maasserver.enum import (
    ARCHITECTURE,
    DISTRO_SERIES,
    NODE_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    PRESEED_TYPE,
    )
from maasserver.models import Config
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
    GENERIC_FILENAME,
    get_curtin_config,
    get_curtin_context,
    get_curtin_installer_url,
    get_curtin_userdata,
    get_enlist_preseed,
    get_hostname_and_path,
    get_node_preseed_context,
    get_preseed,
    get_preseed_context,
    get_preseed_filenames,
    get_preseed_template,
    get_preseed_type_for,
    load_preseed_template,
    PreseedTemplate,
    render_enlistment_preseed,
    render_preseed,
    split_subarch,
    TemplateNotFoundError,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import map_enum
from maastesting.matchers import ContainsAll
from testtools.matchers import (
    AllMatch,
    Contains,
    IsInstance,
    MatchesAll,
    Not,
    StartsWith,
    )
import yaml


class TestSplitSubArch(MAASServerTestCase):
    """Tests for `split_subarch`."""

    def test_split_subarch_returns_list(self):
        self.assertEqual(['amd64'], split_subarch('amd64'))

    def test_split_subarch_splits_sub_architecture(self):
        self.assertEqual(['amd64', 'test'], split_subarch('amd64/test'))


class TestGetHostnameAndPath(MAASServerTestCase):
    """Tests for `get_hostname_and_path`."""

    def test_get_hostname_and_path(self):
        input_and_results = [
            ('http://name.domain/my/path', ('name.domain', '/my/path')),
            ('https://domain/path', ('domain', '/path')),
            ('http://domain/', ('domain', '/')),
            ('http://domain', ('domain', '')),
            ]
        inputs = [input for input, _ in input_and_results]
        results = [result for _, result in input_and_results]
        self.assertEqual(results, map(get_hostname_and_path, inputs))


class TestGetPreseedFilenames(MAASServerTestCase):
    """Tests for `get_preseed_filenames`."""

    def test_get_preseed_filenames_returns_filenames(self):
        hostname = factory.getRandomString()
        prefix = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        arch, subarch = node.architecture.split('/')
        self.assertSequenceEqual(
            [
                '%s_%s_%s_%s_%s' % (prefix, arch, subarch, release, hostname),
                '%s_%s_%s_%s' % (prefix, arch, subarch, release),
                '%s_%s_%s' % (prefix, arch, subarch),
                '%s_%s' % (prefix, arch),
                '%s' % prefix,
                'generic',
            ],
            list(get_preseed_filenames(node, prefix, release, default=True)))

    def test_get_preseed_filenames_if_node_is_None(self):
        release = factory.getRandomString()
        prefix = factory.getRandomString()
        self.assertSequenceEqual(
            [
                '%s_%s' % (prefix, release),
                '%s' % prefix,
            ],
            list(get_preseed_filenames(None, prefix, release)))

    def test_get_preseed_filenames_supports_empty_prefix(self):
        hostname = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        arch, subarch = node.architecture.split('/')
        self.assertSequenceEqual(
            [
                '%s_%s_%s_%s' % (arch, subarch, release, hostname),
                '%s_%s_%s' % (arch, subarch, release),
                '%s_%s' % (arch, subarch),
                '%s' % arch,
            ],
            list(get_preseed_filenames(node, '', release)))

    def test_get_preseed_filenames_returns_list_without_default(self):
        # If default=False is passed to get_preseed_filenames, the
        # returned list won't include the default template name as a
        # last resort template.
        hostname = factory.getRandomString()
        prefix = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        self.assertSequenceEqual(
            'generic',
            list(get_preseed_filenames(
                node, prefix, release, default=True))[-1])

    def test_get_preseed_filenames_returns_list_with_default(self):
        # If default=True is passed to get_preseed_filenames, the
        # returned list will include the default template name as a
        # last resort template.
        hostname = factory.getRandomString()
        prefix = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        self.assertSequenceEqual(
            prefix,
            list(get_preseed_filenames(
                node, prefix, release, default=False))[-1])


class TestConfiguration(MAASServerTestCase):
    """Test for correct configuration of the preseed component."""

    def test_setting_defined(self):
        self.assertThat(
            settings.PRESEED_TEMPLATE_LOCATIONS,
            AllMatch(IsInstance(unicode)))


class TestGetPreseedTemplate(MAASServerTestCase):
    """Tests for `get_preseed_template`."""

    def test_get_preseed_template_returns_None_if_no_template_locations(self):
        # get_preseed_template() returns None when no template locations are
        # defined.
        self.patch(settings, "PRESEED_TEMPLATE_LOCATIONS", [])
        self.assertEqual(
            (None, None),
            get_preseed_template(
                (factory.getRandomString(), factory.getRandomString())))

    def test_get_preseed_template_returns_None_when_no_filenames(self):
        # get_preseed_template() returns None when no filenames are passed in.
        self.patch(settings, "PRESEED_TEMPLATE_LOCATIONS", [self.make_dir()])
        self.assertEqual((None, None), get_preseed_template(()))

    def test_get_preseed_template_find_template_in_first_location(self):
        template_content = factory.getRandomString()
        template_path = self.make_file(contents=template_content)
        template_filename = os.path.basename(template_path)
        locations = [
            os.path.dirname(template_path),
            self.make_dir(),
            ]
        self.patch(settings, "PRESEED_TEMPLATE_LOCATIONS", locations)
        self.assertEqual(
            (template_path, template_content),
            get_preseed_template([template_filename]))

    def test_get_preseed_template_find_template_in_last_location(self):
        template_content = factory.getRandomString()
        template_path = self.make_file(contents=template_content)
        template_filename = os.path.basename(template_path)
        locations = [
            self.make_dir(),
            os.path.dirname(template_path),
            ]
        self.patch(settings, "PRESEED_TEMPLATE_LOCATIONS", locations)
        self.assertEqual(
            (template_path, template_content),
            get_preseed_template([template_filename]))


class TestLoadPreseedTemplate(MAASServerTestCase):
    """Tests for `load_preseed_template`."""

    def setUp(self):
        super(TestLoadPreseedTemplate, self).setUp()
        self.location = self.make_dir()
        self.patch(
            settings, "PRESEED_TEMPLATE_LOCATIONS", [self.location])

    def create_template(self, location, name, content=None):
        # Create a tempita template in the given `self.location` with the
        # given `name`.  If content is not provided, a random content
        # will be put inside the template.
        path = os.path.join(self.location, name)
        rendered_content = None
        if content is None:
            rendered_content = factory.getRandomString()
            content = b'{{def stuff}}%s{{enddef}}{{stuff}}' % rendered_content
        with open(path, "wb") as outf:
            outf.write(content)
        return rendered_content

    def test_load_preseed_template_returns_PreseedTemplate(self):
        name = factory.getRandomString()
        self.create_template(self.location, name)
        node = factory.make_node()
        template = load_preseed_template(node, name)
        self.assertIsInstance(template, PreseedTemplate)

    def test_load_preseed_template_raises_if_no_template(self):
        node = factory.make_node()
        unknown_template_name = factory.getRandomString()
        self.assertRaises(
            TemplateNotFoundError, load_preseed_template, node,
            unknown_template_name)

    def test_load_preseed_template_generic_lookup(self):
        # The template lookup method ends up picking up a template named
        # 'generic' if no more specific template exist.
        content = self.create_template(self.location, GENERIC_FILENAME)
        node = factory.make_node(hostname=factory.getRandomString())
        template = load_preseed_template(node, factory.getRandomString())
        self.assertEqual(content, template.substitute())

    def test_load_preseed_template_prefix_lookup(self):
        # 2nd last in the hierarchy is a template named 'prefix'.
        prefix = factory.getRandomString()
        # Create the generic template.  This one will be ignored due to the
        # presence of a more specific template.
        self.create_template(self.location, GENERIC_FILENAME)
        # Create the 'prefix' template.  This is the one which will be
        # picked up.
        content = self.create_template(self.location, prefix)
        node = factory.make_node(hostname=factory.getRandomString())
        template = load_preseed_template(node, prefix)
        self.assertEqual(content, template.substitute())

    def test_load_preseed_template_node_specific_lookup(self):
        # At the top of the lookup hierarchy is a template specific to this
        # node.  It will be used first if it's present.
        prefix = factory.getRandomString()
        release = factory.getRandomString()
        # Create the generic and 'prefix' templates.  They will be ignored
        # due to the presence of a more specific template.
        self.create_template(self.location, GENERIC_FILENAME)
        self.create_template(self.location, prefix)
        node = factory.make_node(hostname=factory.getRandomString())
        node_template_name = "%s_%s_%s_%s" % (
            prefix, node.architecture.replace('/', '_'),
            release, node.hostname)
        # Create the node-specific template.
        content = self.create_template(self.location, node_template_name)
        template = load_preseed_template(node, prefix, release)
        self.assertEqual(content, template.substitute())

    def test_load_preseed_template_with_inherits(self):
        # A preseed file can "inherit" from another file.
        prefix = factory.getRandomString()
        # Create preseed template.
        master_template_name = factory.getRandomString()
        preseed_content = '{{inherit "%s"}}' % master_template_name
        self.create_template(self.location, prefix, preseed_content)
        master_content = self.create_template(
            self.location, master_template_name)
        node = factory.make_node()
        template = load_preseed_template(node, prefix)
        self.assertEqual(master_content, template.substitute())

    def test_load_preseed_template_parent_lookup_doesnt_include_default(self):
        # The lookup for parent templates does not include the default
        # 'generic' file.
        prefix = factory.getRandomString()
        # Create 'generic' template.  It won't be used because the
        # lookup for parent templates does not use the 'generic' template.
        self.create_template(self.location, GENERIC_FILENAME)
        unknown_master_template_name = factory.getRandomString()
        # Create preseed template.
        preseed_content = '{{inherit "%s"}}' % unknown_master_template_name
        self.create_template(self.location, prefix, preseed_content)
        node = factory.make_node()
        template = load_preseed_template(node, prefix)
        self.assertRaises(
            TemplateNotFoundError, template.substitute)


def make_url(name):
    """Create a fake archive URL."""
    return "http://%s.example.com/%s/" % (
        factory.make_name(name),
        factory.make_name('path'),
        )


class TestPreseedContext(MAASServerTestCase):
    """Tests for `get_preseed_context`."""

    def test_get_preseed_context_contains_keys(self):
        release = factory.getRandomString()
        nodegroup = factory.make_node_group(maas_url=factory.getRandomString())
        context = get_preseed_context(release, nodegroup)
        self.assertItemsEqual(
            ['release', 'metadata_enlist_url', 'server_host', 'server_url',
             'cluster_host', 'main_archive_hostname', 'main_archive_directory',
             'ports_archive_hostname', 'ports_archive_directory',
             'http_proxy'],
            context)

    def test_get_preseed_context_archive_refs(self):
        # urlparse lowercases the hostnames. That should not have any
        # impact but for testing, create lower-case hostnames.
        main_archive = make_url('main_archive')
        ports_archive = make_url('ports_archive')
        Config.objects.set_config('main_archive', main_archive)
        Config.objects.set_config('ports_archive', ports_archive)
        nodegroup = factory.make_node_group(maas_url=factory.getRandomString())
        context = get_preseed_context(factory.make_node(), nodegroup)
        parsed_main_archive = urlparse(main_archive)
        parsed_ports_archive = urlparse(ports_archive)
        self.assertEqual(
            (
                parsed_main_archive.hostname,
                parsed_main_archive.path,
                parsed_ports_archive.hostname,
                parsed_ports_archive.path,
            ),
            (
                context['main_archive_hostname'],
                context['main_archive_directory'],
                context['ports_archive_hostname'],
                context['ports_archive_directory'],
            ))

    def test_preseed_context_cluster_host(self):
        # The cluster_host context variable is derived from the nodegroup.
        release = factory.getRandomString()
        nodegroup = factory.make_node_group(maas_url=factory.getRandomString())
        context = get_preseed_context(release, nodegroup)
        self.assertIsNotNone(context["cluster_host"])
        self.assertEqual(
            nodegroup.get_managed_interface().ip,
            context["cluster_host"])

    def test_preseed_context_cluster_host_if_unmanaged(self):
        # If the nodegroup has no managed interface recorded, the cluster_host
        # context variable is still present and derived from the nodegroup.
        release = factory.getRandomString()
        nodegroup = factory.make_node_group(maas_url=factory.getRandomString())
        for interface in nodegroup.nodegroupinterface_set.all():
            interface.management = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
            interface.save()
        context = get_preseed_context(release, nodegroup)
        self.assertIsNotNone(context["cluster_host"])
        self.assertEqual(
            nodegroup.get_any_interface().ip,
            context["cluster_host"])

    def test_preseed_context_null_cluster_host_if_does_not_exist(self):
        # If there's no nodegroup, the cluster_host context variable is
        # present, but None.
        release = factory.getRandomString()
        context = get_preseed_context(release)
        self.assertIsNone(context["cluster_host"])


class TestNodePreseedContext(MAASServerTestCase):
    """Tests for `get_node_preseed_context`."""

    def test_get_node_preseed_context_contains_keys(self):
        node = factory.make_node()
        release = factory.getRandomString()
        context = get_node_preseed_context(node, release)
        self.assertItemsEqual(
            ['node', 'preseed_data', 'node_disable_pxe_url',
             'node_disable_pxe_data',
             ],
            context)


class TestPreseedTemplate(MAASServerTestCase):
    """Tests for class:`PreseedTemplate`."""

    def test_escape_shell(self):
        template = PreseedTemplate("{{var|escape.shell}}")
        var = "$ ! ()"
        observed = template.substitute(var=var)
        self.assertEqual(quote(var), observed)


class TestRenderPreseed(MAASServerTestCase):
    """Tests for `render_preseed`.

    These tests check that the templates render (i.e. that no variable is
    missing).
    """

    # Create a scenario for each possible value of PRESEED_TYPE except
    # enlistment. Those have their own test case.
    scenarios = [
        (name, {'preseed': value})
        for name, value in map_enum(PRESEED_TYPE).items()
        if not value.startswith('enlist')
    ]

    def test_render_preseed(self):
        node = factory.make_node()
        preseed = render_preseed(node, self.preseed, "precise")
        # The test really is that the preseed is rendered without an
        # error.
        self.assertIsInstance(preseed, bytes)

    def test_get_preseed_uses_nodegroup_maas_url(self):
        ng_url = 'http://%s' % factory.make_hostname()
        ng = factory.make_node_group(maas_url=ng_url)
        maas_url = 'http://%s' % factory.make_hostname()
        node = factory.make_node(
            nodegroup=ng, status=NODE_STATUS.COMMISSIONING)
        self.patch(settings, 'DEFAULT_MAAS_URL', maas_url)
        preseed = render_preseed(node, self.preseed, "precise")
        self.assertThat(
            preseed, MatchesAll(*[Contains(ng_url), Not(Contains(maas_url))]))


class TestRenderEnlistmentPreseed(MAASServerTestCase):
    """Tests for `render_enlistment_preseed`."""

    # Create a scenario for each possible value of PRESEED_TYPE for
    # enlistment. The rest have their own test case.
    scenarios = [
        (name, {'preseed': value})
        for name, value in map_enum(PRESEED_TYPE).items()
        if value.startswith('enlist')
    ]

    def test_render_enlistment_preseed(self):
        preseed = render_enlistment_preseed(self.preseed, "precise")
        # The test really is that the preseed is rendered without an
        # error.
        self.assertIsInstance(preseed, bytes)

    def test_render_enlistment_preseed_valid_yaml(self):
        preseed = render_enlistment_preseed(self.preseed, "precise")
        self.assertTrue(yaml.safe_load(preseed))

    def test_get_preseed_uses_nodegroup_maas_url(self):
        ng_url = 'http://%s' % factory.make_hostname()
        maas_url = 'http://%s' % factory.make_hostname()
        self.patch(settings, 'DEFAULT_MAAS_URL', maas_url)
        nodegroup = factory.make_node_group(maas_url=ng_url)
        preseed = render_enlistment_preseed(
            self.preseed, "precise", nodegroup=nodegroup)
        self.assertThat(
            preseed, MatchesAll(*[Contains(ng_url), Not(Contains(maas_url))]))


class TestGetCurtinUserData(MAASServerTestCase):
    """Tests for `get_curtin_userdata`."""

    def test_get_curtin_userdata(self):
        node = factory.make_node()
        node.use_fastpath_installer()
        user_data = get_curtin_userdata(node)
        # Just check that the user data looks good.
        self.assertIn("PREFIX='curtin'", user_data)


class TestCurtinUtilities(MAASServerTestCase):
    """Tests for the curtin-related utilities."""

    def test_get_curtin_config(self):
        node = factory.make_node()
        node.use_fastpath_installer()
        config = get_curtin_config(node)
        self.assertThat(
            config,
            ContainsAll(
                [
                    'mode: reboot',
                    "debconf_selections:",
                ]
            ))

    def test_get_curtin_context(self):
        node = factory.make_node()
        node.use_fastpath_installer()
        context = get_curtin_context(node)
        self.assertItemsEqual(['curtin_preseed'], context)
        self.assertIn('cloud-init', context['curtin_preseed'])

    def test_get_curtin_installer_url(self):
        # Exclude DISTRO_SERIES.default. It's a special value that defers
        # to a run-time setting which we don't provide in this test.
        series = factory.getRandomEnum(
            DISTRO_SERIES, but_not=DISTRO_SERIES.default)
        arch = factory.getRandomEnum(ARCHITECTURE)
        node = factory.make_node(architecture=arch, distro_series=series)
        installer_url = get_curtin_installer_url(node)
        self.assertEqual(
            'http://%s/MAAS/static/images/%s/%s/xinstall/root.tar.gz' % (
                node.nodegroup.get_managed_interface().ip, arch, series),
            installer_url)

    def test_get_preseed_type_for(self):
        normal = factory.make_node()
        normal.use_traditional_installer()
        fpi = factory.make_node()
        fpi.use_fastpath_installer()

        self.assertEqual(PRESEED_TYPE.DEFAULT, get_preseed_type_for(normal))
        self.assertEqual(PRESEED_TYPE.CURTIN, get_preseed_type_for(fpi))


class TestRenderPreseedArchives(MAASServerTestCase):
    """Test that the default preseed contains the default mirrors."""

    def test_render_preseed_uses_default_archives_intel(self):
        nodes = [
            factory.make_node(architecture=ARCHITECTURE.i386),
            factory.make_node(architecture=ARCHITECTURE.amd64),
            ]
        default_snippets = [
            "d-i     mirror/http/hostname string archive.ubuntu.com",
            "d-i     mirror/http/directory string /ubuntu",
            ]
        for node in nodes:
            preseed = render_preseed(node, PRESEED_TYPE.DEFAULT, "precise")
            self.assertThat(preseed, ContainsAll(default_snippets))

    def test_render_preseed_uses_default_archives_arm(self):
        node = factory.make_node(architecture=ARCHITECTURE.armhf_highbank)
        default_snippets = [
            "d-i     mirror/http/hostname string ports.ubuntu.com",
            "d-i     mirror/http/directory string /ubuntu-ports",
            ]
        preseed = render_preseed(node, PRESEED_TYPE.DEFAULT, "precise")
        self.assertThat(preseed, ContainsAll(default_snippets))


class TestPreseedProxy(MAASServerTestCase):

    def test_preseed_uses_default_proxy(self):
        server_host = factory.make_hostname()
        url = 'http://%s:%d/%s' % (
            server_host, factory.getRandomPort(), factory.getRandomString())
        self.patch(settings, 'DEFAULT_MAAS_URL', url)
        expected_proxy_statement = (
            "mirror/http/proxy string http://%s:8000" % server_host)
        preseed = render_preseed(
            factory.make_node(), PRESEED_TYPE.DEFAULT, "precise")
        self.assertIn(expected_proxy_statement, preseed)

    def test_preseed_uses_configured_proxy(self):
        http_proxy = 'http://%s:%d/%s' % (
            factory.getRandomString(), factory.getRandomPort(),
            factory.getRandomString())
        Config.objects.set_config('http_proxy', http_proxy)
        expected_proxy_statement = (
            "mirror/http/proxy string %s" % http_proxy)
        preseed = render_preseed(
            factory.make_node(), PRESEED_TYPE.DEFAULT, "precise")
        self.assertIn(expected_proxy_statement, preseed)


class TestPreseedMethods(MAASServerTestCase):
    """Tests for `get_enlist_preseed` and `get_preseed`.

    These tests check that the preseed templates render and 'look right'.
    """

    def test_get_preseed_returns_default_preseed(self):
        node = factory.make_node()
        preseed = get_preseed(node)
        self.assertIn('preseed/late_command', preseed)

    def test_get_preseed_returns_curtin_preseed(self):
        node = factory.make_node()
        node.use_fastpath_installer()
        preseed = get_preseed(node)
        curtin_url = reverse('curtin-metadata')
        self.assertIn(curtin_url, preseed)

    def test_get_enlist_preseed_returns_enlist_preseed(self):
        preseed = get_enlist_preseed()
        self.assertTrue(preseed.startswith('#cloud-config'))

    def test_get_preseed_returns_commissioning_preseed(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = get_preseed(node)
        self.assertIn('#cloud-config', preseed)


class TestPreseedURLs(MAASServerTestCase):
    """Tests for functions that return preseed URLs."""

    def test_compose_enlistment_preseed_url_links_to_enlistment_preseed(self):
        response = self.client.get(compose_enlistment_preseed_url())
        self.assertEqual(
            (httplib.OK, get_enlist_preseed()),
            (response.status_code, response.content))

    def test_compose_enlistment_preseed_url_returns_absolute_link(self):
        url = 'http://%s' % factory.make_name('host')
        self.patch(settings, 'DEFAULT_MAAS_URL', url)
        self.assertThat(
            compose_enlistment_preseed_url(), StartsWith(url))

    def test_compose_preseed_url_links_to_preseed_for_node(self):
        node = factory.make_node()
        response = self.client.get(compose_preseed_url(node))
        self.assertEqual(
            (httplib.OK, get_preseed(node)),
            (response.status_code, response.content))

    def test_compose_preseed_url_returns_absolute_link(self):
        self.assertThat(
            compose_preseed_url(factory.make_node()),
            StartsWith('http://'))

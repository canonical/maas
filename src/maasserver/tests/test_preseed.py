# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
    NODE_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    PRESEED_TYPE,
    )
from maasserver.exceptions import MAASAPIException
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
    pick_cluster_controller_address,
    PreseedTemplate,
    render_enlistment_preseed,
    render_preseed,
    split_subarch,
    TemplateNotFoundError,
    )
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import map_enum
from maasserver.utils.network import make_network
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from testtools.matchers import (
    AllMatch,
    Contains,
    ContainsAll,
    HasLength,
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
        osystem = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        arch, subarch = node.architecture.split('/')
        self.assertSequenceEqual(
            [
                '%s_%s_%s_%s_%s_%s' % (
                    prefix, osystem, arch, subarch, release, hostname),
                '%s_%s_%s_%s_%s' % (prefix, osystem, arch, subarch, release),
                '%s_%s_%s_%s' % (prefix, osystem, arch, subarch),
                '%s_%s_%s' % (prefix, osystem, arch),
                '%s_%s' % (prefix, osystem),
                '%s' % prefix,
                'generic',
            ],
            list(get_preseed_filenames(
                node, prefix, osystem, release, default=True)))

    def test_get_preseed_filenames_if_node_is_None(self):
        osystem = factory.getRandomString()
        release = factory.getRandomString()
        prefix = factory.getRandomString()
        self.assertSequenceEqual(
            [
                '%s_%s_%s' % (prefix, osystem, release),
                '%s_%s' % (prefix, osystem),
                '%s' % prefix,
            ],
            list(get_preseed_filenames(None, prefix, osystem, release)))

    def test_get_preseed_filenames_supports_empty_prefix(self):
        hostname = factory.getRandomString()
        osystem = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        arch, subarch = node.architecture.split('/')
        self.assertSequenceEqual(
            [
                '%s_%s_%s_%s_%s' % (osystem, arch, subarch, release, hostname),
                '%s_%s_%s_%s' % (osystem, arch, subarch, release),
                '%s_%s_%s' % (osystem, arch, subarch),
                '%s_%s' % (osystem, arch),
                '%s' % osystem,
            ],
            list(get_preseed_filenames(node, '', osystem, release)))

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
        osystem = factory.getRandomString()
        release = factory.getRandomString()
        # Create the generic and 'prefix' templates.  They will be ignored
        # due to the presence of a more specific template.
        self.create_template(self.location, GENERIC_FILENAME)
        self.create_template(self.location, prefix)
        node = factory.make_node(hostname=factory.getRandomString())
        node_template_name = "%s_%s_%s_%s_%s" % (
            prefix, osystem, node.architecture.replace('/', '_'),
            release, node.hostname)
        # Create the node-specific template.
        content = self.create_template(self.location, node_template_name)
        template = load_preseed_template(node, prefix, osystem, release)
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


class TestPickClusterControllerAddress(MAASServerTestCase):
    """Tests for `pick_cluster_controller_address`."""

    def make_bare_nodegroup(self):
        """Create `NodeGroup` without interfaces."""
        nodegroup = factory.make_node_group()
        nodegroup.nodegroupinterface_set.all().delete()
        return nodegroup

    def make_nodegroupinterface(self, nodegroup, ip,
                                mgt=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED,
                                subnet_mask='255.255.255.0'):
        """Create a `NodeGroupInterface` with a given IP address.

        Other network settings are derived from the IP address.
        """
        network = make_network(ip, subnet_mask)
        return factory.make_node_group_interface(
            nodegroup=nodegroup, management=mgt, network=network, ip=ip,
            subnet_mask=subnet_mask)

    def make_lease_for_node(self, node, ip=None):
        """Create a `MACAddress` and corresponding `DHCPLease` for `node`."""
        mac = factory.make_mac_address(node=node).mac_address
        factory.make_dhcp_lease(nodegroup=node.nodegroup, mac=mac, ip=ip)

    def test_returns_only_interface(self):
        node = factory.make_node()
        [interface] = list(node.nodegroup.nodegroupinterface_set.all())

        address = pick_cluster_controller_address(node)

        self.assertIsNotNone(address)
        self.assertEqual(interface.ip, address)

    def test_picks_interface_on_matching_network(self):
        nearest_address = '10.99.1.1'
        nodegroup = self.make_bare_nodegroup()
        self.make_nodegroupinterface(nodegroup, '192.168.11.1')
        self.make_nodegroupinterface(nodegroup, nearest_address)
        self.make_nodegroupinterface(nodegroup, '192.168.22.1')
        node = factory.make_node(nodegroup=nodegroup)
        self.make_lease_for_node(node, '192.168.33.101')
        self.make_lease_for_node(node, '10.99.1.105')
        self.make_lease_for_node(node, '192.168.44.101')
        self.assertEqual('10.99.1.1', pick_cluster_controller_address(node))

    def test_prefers_matching_network_over_managed_interface(self):
        nodegroup = self.make_bare_nodegroup()
        self.make_nodegroupinterface(
            nodegroup, '10.100.100.1',
            mgt=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        self.make_nodegroupinterface(nodegroup, '10.100.101.1')
        node = factory.make_node(nodegroup=nodegroup)
        self.make_lease_for_node(node, '10.100.101.99')
        self.assertEqual('10.100.101.1', pick_cluster_controller_address(node))

    def test_prefers_managed_interface_over_unmanaged_interface(self):
        nodegroup = self.make_bare_nodegroup()
        factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        best_interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)

        address = pick_cluster_controller_address(
            factory.make_node(nodegroup=nodegroup))

        self.assertIsNotNone(address)
        self.assertEqual(best_interface.ip, address)

    def test_prefers_dns_managed_interface_over_unmanaged_interface(self):
        nodegroup = self.make_bare_nodegroup()
        factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        best_interface = factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)

        address = pick_cluster_controller_address(
            factory.make_node(nodegroup=nodegroup))

        self.assertIsNotNone(address)
        self.assertEqual(best_interface.ip, address)

    def test_returns_None_if_no_interfaces(self):
        nodegroup = factory.make_node_group()
        nodegroup.nodegroupinterface_set.all().delete()
        self.assertIsNone(
            pick_cluster_controller_address(
                factory.make_node(nodegroup=nodegroup)))

    def test_makes_consistent_choice(self):
        # Not a very thorough test, but we want at least a little bit of
        # predictability.
        nodegroup = factory.make_node_group(
            NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        for _ in range(5):
            factory.make_node_group_interface(
                nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        node = factory.make_node(nodegroup=nodegroup)
        self.assertEqual(
            pick_cluster_controller_address(node),
            pick_cluster_controller_address(node))


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
            ['osystem', 'release', 'metadata_enlist_url', 'server_host',
             'server_url', 'main_archive_hostname', 'main_archive_directory',
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


class TestNodePreseedContext(MAASServerTestCase):
    """Tests for `get_node_preseed_context`."""

    def test_get_node_preseed_context_contains_keys(self):
        node = factory.make_node()
        release = factory.getRandomString()
        context = get_node_preseed_context(node, release)
        self.assertItemsEqual(
            ['driver', 'driver_package', 'node',
             'node_disable_pxe_data', 'node_disable_pxe_url',
             'preseed_data', 'third_party_drivers',
             ],
            context)

    def test_context_contains_third_party_drivers(self):
        node = factory.make_node()
        release = factory.getRandomString()
        enable_third_party_drivers = factory.getRandomBoolean()
        Config.objects.set_config(
            'enable_third_party_drivers', enable_third_party_drivers)
        context = get_node_preseed_context(node, release)
        self.assertEqual(
            enable_third_party_drivers,
            context['third_party_drivers'])


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
        arch, subarch = node.architecture.split('/')
        factory.make_boot_image(
            osystem=node.get_osystem(),
            architecture=arch, subarchitecture=subarch,
            release=node.get_distro_series(), purpose='xinstall',
            nodegroup=node.nodegroup)
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

    def make_fastpath_node(self, main_arch=None):
        """Return a `Node`, with FPI enabled, and the given main architecture.

        :param main_arch: A main architecture, such as `i386` or `armhf`.  A
            subarchitecture will be made up.
        """
        if main_arch is None:
            main_arch = factory.make_name('arch')
        arch = '%s/%s' % (main_arch, factory.make_name('subarch'))
        node = factory.make_node(architecture=arch)
        node.use_fastpath_installer()
        return node

    def extract_archive_setting(self, userdata):
        """Extract the `ubuntu_archive` setting from `userdata`."""
        userdata_lines = []
        for line in userdata.splitlines():
            line = line.strip()
            if line.startswith('ubuntu_archive'):
                userdata_lines.append(line)
        self.assertThat(userdata_lines, HasLength(1))
        [userdata_line] = userdata_lines
        key, value = userdata_line.split(':', 1)
        return value.strip()

    def summarise_url(self, url):
        """Return just the hostname and path from `url`, normalised."""
        # This is needed because the userdata deliberately makes some minor
        # changes to the archive URLs, making it harder to recognise which
        # archive they use: slashes are added, schemes are hard-coded.
        parsed_result = urlparse(url)
        return parsed_result.netloc, parsed_result.path.strip('/')

    def test_get_curtin_config_uses_main_archive_for_i386(self):
        node = self.make_fastpath_node('i386')
        userdata = get_curtin_config(node)
        self.assertEqual(
            self.summarise_url(Config.objects.get_config('main_archive')),
            self.summarise_url(self.extract_archive_setting(userdata)))

    def test_get_curtin_config_uses_main_archive_for_amd64(self):
        node = self.make_fastpath_node('amd64')
        userdata = get_curtin_config(node)
        self.assertEqual(
            self.summarise_url(Config.objects.get_config('main_archive')),
            self.summarise_url(self.extract_archive_setting(userdata)))

    def test_get_curtin_config_uses_ports_archive_for_other_arch(self):
        node = self.make_fastpath_node()
        userdata = get_curtin_config(node)
        self.assertEqual(
            self.summarise_url(Config.objects.get_config('ports_archive')),
            self.summarise_url(self.extract_archive_setting(userdata)))

    def test_get_curtin_context(self):
        node = factory.make_node()
        node.use_fastpath_installer()
        context = get_curtin_context(node)
        self.assertItemsEqual(['curtin_preseed'], context)
        self.assertIn('cloud-init', context['curtin_preseed'])

    def test_get_curtin_installer_url_returns_url(self):
        osystem = factory.getRandomOS()
        series = factory.getRandomRelease(osystem)
        architecture = make_usable_architecture(self)
        node = factory.make_node(
            osystem=osystem.name, architecture=architecture,
            distro_series=series)
        arch, subarch = architecture.split('/')
        boot_image = factory.make_boot_image(
            osystem=osystem.name, architecture=arch,
            subarchitecture=subarch, release=series,
            purpose='xinstall', nodegroup=node.nodegroup)

        installer_url = get_curtin_installer_url(node)

        [interface] = node.nodegroup.get_managed_interfaces()
        self.assertEqual(
            'http://%s/MAAS/static/images/%s/%s/%s/%s/%s/root-tgz' % (
                interface.ip, osystem.name, arch, subarch,
                series, boot_image.label),
            installer_url)

    def test_get_curtin_installer_url_fails_if_no_boot_image(self):
        osystem = factory.getRandomOS()
        series = factory.getRandomRelease(osystem)
        architecture = make_usable_architecture(self)
        node = factory.make_node(
            osystem=osystem.name,
            architecture=architecture, distro_series=series)
        # Generate a boot image with a different arch/subarch.
        factory.make_boot_image(
            osystem=osystem.name,
            architecture=factory.make_name('arch'),
            subarchitecture=factory.make_name('subarch'), release=series,
            purpose='xinstall', nodegroup=node.nodegroup)

        error = self.assertRaises(
            MAASAPIException, get_curtin_installer_url, node)
        arch, subarch = architecture.split('/')
        msg = (
            "No image could be found for the given selection: "
            "os=%s, arch=%s, subarch=%s, series=%s, purpose=xinstall." % (
                osystem.name,
                arch,
                subarch,
                node.get_distro_series(),
            ))
        self.assertIn(msg, "%s" % error)

    def test_get_preseed_type_for_commissioning(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        self.assertEqual(
            PRESEED_TYPE.COMMISSIONING, get_preseed_type_for(node))

    def test_get_preseed_type_for_default(self):
        osystem = make_usable_osystem(
            self, purposes=[BOOT_IMAGE_PURPOSE.INSTALL])
        node = factory.make_node(
            osystem=osystem.name,
            distro_series=factory.getRandomRelease(osystem))
        node.use_traditional_installer()
        self.assertEqual(
            PRESEED_TYPE.DEFAULT, get_preseed_type_for(node))

    def test_get_preseed_type_for_curtin(self):
        osystem = make_usable_osystem(
            self, purposes=[BOOT_IMAGE_PURPOSE.XINSTALL])
        node = factory.make_node(
            osystem=osystem.name,
            distro_series=factory.getRandomRelease(osystem))
        node.use_fastpath_installer()
        self.assertEqual(
            PRESEED_TYPE.CURTIN, get_preseed_type_for(node))

    def test_get_preseed_type_for_default_when_curtin_not_supported(self):
        osystem = make_usable_osystem(
            self, purposes=[BOOT_IMAGE_PURPOSE.INSTALL])
        node = factory.make_node(
            osystem=osystem.name,
            distro_series=factory.getRandomRelease(osystem))
        node.use_fastpath_installer()
        self.assertEqual(
            PRESEED_TYPE.DEFAULT, get_preseed_type_for(node))

    def test_get_preseed_type_for_curtin_when_default_not_supported(self):
        osystem = make_usable_osystem(
            self, purposes=[BOOT_IMAGE_PURPOSE.XINSTALL])
        node = factory.make_node(
            osystem=osystem.name,
            distro_series=factory.getRandomRelease(osystem))
        node.use_traditional_installer()
        self.assertEqual(
            PRESEED_TYPE.CURTIN, get_preseed_type_for(node))


class TestRenderPreseedArchives(MAASServerTestCase):
    """Test that the default preseed contains the default mirrors."""

    def test_render_preseed_uses_default_archives_intel(self):
        nodes = [
            factory.make_node(
                architecture=make_usable_architecture(
                    self, arch_name="i386", subarch_name="generic")),
            factory.make_node(
                architecture=make_usable_architecture(
                    self, arch_name="amd64", subarch_name="generic")),
            ]
        default_snippets = [
            "d-i     mirror/http/hostname string archive.ubuntu.com",
            "d-i     mirror/http/directory string /ubuntu",
            ]
        for node in nodes:
            preseed = render_preseed(node, PRESEED_TYPE.DEFAULT, "precise")
            self.assertThat(preseed, ContainsAll(default_snippets))

    def test_render_preseed_uses_default_archives_arm(self):
        node = factory.make_node(architecture=make_usable_architecture(
            self, arch_name="armhf", subarch_name="generic"))
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

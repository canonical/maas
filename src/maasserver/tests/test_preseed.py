# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test `maasserver.preseed` and related bits and bobs."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os
from pipes import quote

from django.conf import settings
from maasserver.enum import (
    NODE_STATUS,
    PRESEED_TYPE,
    )
from maasserver.models import Config
from maasserver.preseed import (
    GENERIC_FILENAME,
    get_enlist_preseed,
    get_maas_server_host,
    get_preseed,
    get_preseed_context,
    get_preseed_filenames,
    get_preseed_template,
    load_preseed_template,
    PreseedTemplate,
    render_preseed,
    split_subarch,
    TemplateNotFoundError,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.utils import map_enum
from testtools.matchers import (
    AllMatch,
    IsInstance,
    )


class TestSplitSubArch(TestCase):
    """Tests for `split_subarch`."""

    def test_split_subarch_returns_list(self):
        self.assertEqual(['amd64'], split_subarch('amd64'))

    def test_split_subarch_splits_sub_architecture(self):
        self.assertEqual(['amd64', 'test'], split_subarch('amd64/test'))


class TestGetPreseedFilenames(TestCase):
    """Tests for `get_preseed_filenames`."""

    def test_get_preseed_filenames_returns_filenames(self):
        hostname = factory.getRandomString()
        prefix = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        self.assertSequenceEqual(
            [
                '%s_%s_%s_%s' % (prefix, node.architecture, release, hostname),
                '%s_%s_%s' % (prefix, node.architecture, release),
                '%s_%s' % (prefix, node.architecture),
                '%s' % prefix,
                'generic',
            ],
            list(get_preseed_filenames(node, prefix, release, default=True)))

    def test_get_preseed_filenames_returns_filenames_with_subarch(self):
        arch = factory.getRandomString()
        subarch = factory.getRandomString()
        fake_arch = '%s/%s' % (arch, subarch)
        hostname = factory.getRandomString()
        prefix = factory.getRandomString()
        release = factory.getRandomString()
        node = factory.make_node(hostname=hostname)
        # Set an architecture of the form '%s/%s' i.e. with a
        # sub-architecture.
        node.architecture = fake_arch
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
        self.assertSequenceEqual(
            [
                '%s_%s_%s' % (node.architecture, release, hostname),
                '%s_%s' % (node.architecture, release),
                '%s' % node.architecture,
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


class TestConfiguration(TestCase):
    """Test for correct configuration of the preseed component."""

    def test_setting_defined(self):
        self.assertThat(
            settings.PRESEED_TEMPLATE_LOCATIONS,
            AllMatch(IsInstance(basestring)))


class TestGetPreseedTemplate(TestCase):
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


class TestLoadPreseedTemplate(TestCase):
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
            prefix, node.architecture, release, node.hostname)
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


class TestGetMAASServerHost(TestCase):
    """Tests for `get_maas_server_host`."""

    def test_get_maas_server_host_returns_host(self):
        Config.objects.set_config('maas_url', 'http://example.com/path')
        self.assertEqual('example.com', get_maas_server_host())

    def test_get_maas_server_host_strips_out_port(self):
        Config.objects.set_config(
            'maas_url', 'http://example.com:%d' % factory.getRandomPort())
        self.assertEqual('example.com', get_maas_server_host())


class TestPreseedContext(TestCase):
    """Tests for `get_preseed_context`."""

    def test_get_preseed_context_contains_keys(self):
        node = factory.make_node()
        release = factory.getRandomString()
        context = get_preseed_context(node, release)
        self.assertItemsEqual(
            ['node', 'release', 'server_host', 'preseed_data',
             'node_disable_pxe_url', 'node_disable_pxe_data'],
            context)

    def test_get_preseed_context_if_node_None(self):
        # If the provided Node is None (when're in the context of an
        # enlistment preseed) the returned context does not include the
        # node context.
        release = factory.getRandomString()
        context = get_preseed_context(None, release)
        self.assertItemsEqual(
            ['release', 'server_host'],
            context)


class TestPreseedTemplate(TestCase):
    """Tests for class:`PreseedTemplate`."""

    def test_escape_shell(self):
        template = PreseedTemplate("{{var|escape.shell}}")
        var = "$ ! ()"
        observed = template.substitute(var=var)
        self.assertEqual(quote(var), observed)


class TestRenderPreseed(TestCase):
    """Tests for `render_preseed`.

    These tests check that the templates render (i.e. that no variable is
    missing).
    """

    # Create a scenario for each possible value of PRESEED_TYPE.
    scenarios = [
        (name, {'preseed': value})
        for name, value in map_enum(PRESEED_TYPE).items()]

    def test_render_preseed(self):
        node = factory.make_node()
        preseed = render_preseed(node, self.preseed, "precise")
        # The test really is that the preseed is rendered without an
        # error.
        self.assertIsInstance(preseed, str)


class TestPreseedMethods(TestCase):
    """Tests for `get_enlist_preseed` and `get_preseed`.

    These tests check that the preseed templates render and 'look right'.
    """

    def test_get_preseed_returns_default_preseed(self):
        node = factory.make_node()
        preseed = get_preseed(node)
        self.assertIn('preseed/late_command', preseed)

    def test_get_enlist_preseed_returns_enlist_preseed(self):
        preseed = get_enlist_preseed()
        self.assertIn('maas-enlist-udeb', preseed)

    def test_get_preseed_returns_commissioning_preseed(self):
        node = factory.make_node(status=NODE_STATUS.COMMISSIONING)
        preseed = get_preseed(node)
        self.assertIn('cloud-init', preseed)

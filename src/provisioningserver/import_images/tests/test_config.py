# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for import scripts' configuration handling."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import os.path
from subprocess import CalledProcessError

from maastesting.factory import factory
from maastesting.utils import (
    age_file,
    get_write_time,
    )
from provisioningserver.config import Config
from provisioningserver.import_images import config as config_module
from provisioningserver.import_images.config import (
    DEFAULTS,
    load_ephemerals_config,
    maybe_update_config,
    parse_legacy_config,
    )
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.testing.testcase import PservTestCase


def make_var_name():
    """Make up an environment variable name (but don't define the variable)."""
    return factory.make_name('VAR', sep='_')


def make_option_and_value():
    """Make up an environment variable name and value."""
    return make_var_name(), factory.getRandomString()


def make_legacy_config(testcase, options):
    """Create a legacy config file containing the given options.

    The config file will be patched into `parse_legacy_config` for the
    duration of the ongoing test.

    This does not do any kind of escaping.  If you want your value
    single-quoted, for example, add the the quotes in `options`.
    """
    contents = ''.join(
        'export %s=%s\n' % (variable, value)
        for variable, value in options.iteritems())
    legacy_config = testcase.make_file(contents=contents.encode('utf-8'))
    testcase.patch(config_module, 'EPHEMERALS_LEGACY_CONFIG', legacy_config)
    return legacy_config


class TestParseLegacyConfig(PservTestCase):

    def test_parses_legacy_config(self):
        variable, value = make_option_and_value()
        make_legacy_config(self, {variable: value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_returns_unicode(self):
        variable, value = make_option_and_value()
        make_legacy_config(self, {variable: value})

        config = parse_legacy_config({variable})
        self.assertIsInstance(config.keys()[0], unicode)
        self.assertIsInstance(config.values()[0], unicode)

    def test_handles_equals_signs(self):
        variable = make_var_name()
        value = '=with=more=equals=signs'
        make_legacy_config(self, {variable: value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_handles_multiple_variables(self):
        options = dict(make_option_and_value() for counter in range(4))
        make_legacy_config(self, options)
        self.assertEqual(options, parse_legacy_config(options))

    def test_treats_single_quoted_values_as_single_quoted(self):
        variable = make_var_name()
        value = 'value "with double-quotes" in the middle'
        make_legacy_config(self, {variable: "'%s'" % value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_treats_double_quoted_values_as_double_quoted(self):
        variable = make_var_name()
        value = "value 'with single-quotes' in the middle"
        make_legacy_config(self, {variable: '"%s"' % value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_handles_newlines_in_values(self):
        variable = make_var_name()
        value = '\nNEW!\nnow with extra line breaks'
        make_legacy_config(self, {variable: "'%s'" % value})

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_skips_unwanted_options(self):
        variable, value = make_option_and_value()
        make_legacy_config(self, dict([
            (variable, value),
            make_option_and_value(),
            make_option_and_value(),
            ]))

        self.assertEqual(
            {variable: value},
            parse_legacy_config({variable}))

    def test_skips_unset_options(self):
        make_legacy_config(self, dict([make_option_and_value()]))
        self.assertEqual({}, parse_legacy_config({make_var_name()}))

    def test_returns_empty_if_there_is_no_legacy_config(self):
        non_config = os.path.join(self.make_dir(), factory.make_name())
        self.patch(config_module, 'EPHEMERALS_LEGACY_CONFIG', non_config)

        self.assertEqual({}, parse_legacy_config({make_var_name()}))

    def test_reports_failure_in_legacy_config(self):
        make_legacy_config(self, {make_var_name(): 'x ; exit 1'})

        self.assertRaises(
            CalledProcessError,
            parse_legacy_config, dict([make_option_and_value()]))


class TestMaybeUpdateConfig(PservTestCase):

    def test_populates_new_config_from_legacy(self):
        arches = [factory.make_name('arch') for counter in range(3)]
        releases = [factory.make_name('release') for counter in range(3)]
        legacy_options = {
            'DATA_DIR': factory.getRandomString(),
            'ARCHES': "'%s'" % ' '.join(arches),
            'RELEASES': "'%s'" % ' '.join(releases),
            'TARGET_NAME_PREFIX': factory.getRandomString(),
        }
        make_legacy_config(self, legacy_options)
        config = {'boot': {'ephemeral': {}}}

        changed = maybe_update_config(config)

        self.assertTrue(changed)
        self.assertEqual(
            {
                'directory': legacy_options['DATA_DIR'],
                'arches': ' '.join(arches),
                'releases': ' '.join(releases),
                'target_name_prefix': legacy_options['TARGET_NAME_PREFIX'],
            },
            config['boot']['ephemeral'])

    def test_does_nothing_if_new_config_is_populated(self):
        prefix = factory.getRandomString()
        config = {'boot': {'ephemeral': {'target_name_prefix': prefix}}}
        make_legacy_config(self, {
            'directory': factory.getRandomString(),
            'arches': factory.make_name('arch'),
            'releases': factory.make_name('release'),
            'target_name_prefix': factory.getRandomString(),
            })

        changed = maybe_update_config(config)

        self.assertFalse(changed)
        self.assertEqual(
            {'boot': {'ephemeral': {'target_name_prefix': prefix}}},
            config)

    def test_does_nothing_if_legacy_config_has_no_items(self):
        make_legacy_config(self, {})
        config = {'boot': {'ephemeral': {}}}

        changed = maybe_update_config(config)

        self.assertFalse(changed)
        self.assertEqual({'boot': {'ephemeral': {}}}, config)

    def test_uses_defaults(self):
        make_legacy_config(
            self, {'TARBALL_CACHE_D': factory.getRandomString()})
        config = {'boot': {'ephemeral': {}}}

        changed = maybe_update_config(config)

        self.assertTrue(changed)
        self.assertEqual(
            {'boot': {'ephemeral': DEFAULTS}},
            config)


class TestLoadEphemeralsConfig(PservTestCase):

    def test_loads_existing_config(self):
        data_dir = self.make_dir()
        arches = [factory.make_name('arch')]
        releases = [factory.make_name('release')]
        prefix = factory.getRandomString()
        self.useFixture(ConfigFixture(
            {
                'boot': {
                    'ephemeral': {
                        'directory': data_dir,
                        'arches': arches,
                        'releases': releases,
                        'target_name_prefix': prefix,
                    },
                },
            }))
        # Make it look as if the config file hasn't been changed for a day.
        # That way we can check that loading the config didn't modify it.
        age_file(Config.DEFAULT_FILENAME, 60 * 60 * 24)
        config_last_modified = get_write_time(Config.DEFAULT_FILENAME)
        make_legacy_config(self, {'directory': self.make_dir()})

        config = load_ephemerals_config()

        self.assertEqual(
            {
                'directory': data_dir,
                'arches': arches,
                'releases': releases,
                'target_name_prefix': prefix,
            },
            config['boot']['ephemeral'])
        self.assertEqual(
            config_last_modified,
            get_write_time(Config.DEFAULT_FILENAME))

    def test_converts_legacy_config_if_needed(self):
        data_dir = self.make_dir()
        arch = factory.make_name('arch')
        releas = factory.make_name('release')
        prefix = factory.getRandomString()
        self.useFixture(ConfigFixture({'boot': {'ephemeral': {}}}))
        make_legacy_config(self, {
            'DATA_DIR': data_dir,
            'ARCHES': arch,
            'RELEASES': releas,
            'TARGET_NAME_PREFIX': prefix,
            })
        # Make it look as if the config file hasn't been changed for a day.
        # That way we can easily check that it's been rewritten.
        age_file(Config.DEFAULT_FILENAME, 60 * 60 * 24)
        config_last_modified = get_write_time(Config.DEFAULT_FILENAME)

        config = load_ephemerals_config()

        self.assertEqual(
            {
                'directory': data_dir,
                'arches': [arch],
                'releases': [releas],
                'target_name_prefix': prefix,
            },
            config['boot']['ephemeral'])
        self.assertLess(
            config_last_modified,
            get_write_time(Config.DEFAULT_FILENAME))

# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Config` class and friends."""

__all__ = []

from socket import gethostname

from django.db import IntegrityError
from fixtures import TestWithFixtures
from maasserver.models import Config
import maasserver.models.config
from maasserver.models.config import get_default_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class ConfigDefaultTest(MAASServerTestCase, TestWithFixtures):
    """Test config default values."""

    def test_default_config_maas_name(self):
        default_config = get_default_config()
        self.assertEqual(gethostname(), default_config['maas_name'])

    def test_defaults(self):
        expected = get_default_config()
        observed = {
            name: Config.objects.get_config(name)
            for name in expected
            }

        # Test isolation is not what it ought to be, so we have to exclude
        # rpc_shared_secret here for now. Attempts to improve isolation have
        # so far resulted in random unreproducible test failures. See the
        # merge proposal for lp:~allenap/maas/increased-test-isolation.
        self.assertIn("rpc_shared_secret", expected)
        del expected["rpc_shared_secret"]
        self.assertIn("rpc_shared_secret", observed)
        del observed["rpc_shared_secret"]

        self.assertEqual(expected, observed)


class CallRecorder:
    """A utility class which tracks the calls to its 'call' method and
    stores the arguments given to 'call' in 'self.calls'.
    """

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append([args, kwargs])


class ConfigTest(MAASServerTestCase):
    """Testing of the :class:`Config` model and its related manager class."""

    def test_config_name_uniqueness_enforced(self):
        name = factory.make_name('name')
        Config.objects.create(name=name, value=factory.make_name('value'))
        self.assertRaises(
            IntegrityError,
            Config.objects.create, name=name, value=factory.make_name('value'))

    def test_manager_get_config_found(self):
        Config.objects.create(name='name', value='config')
        config = Config.objects.get_config('name')
        self.assertEqual('config', config)

    def test_manager_get_config_not_found(self):
        config = Config.objects.get_config('name', 'default value')
        self.assertEqual('default value', config)

    def test_manager_get_config_not_found_none(self):
        config = Config.objects.get_config('name')
        self.assertIsNone(config)

    def test_manager_get_config_not_found_in_default_config(self):
        name = factory.make_string()
        value = factory.make_string()
        self.patch(maasserver.models.config, "DEFAULT_CONFIG", {name: value})
        config = Config.objects.get_config(name, None)
        self.assertEqual(value, config)

    def test_default_config_cannot_be_changed(self):
        name = factory.make_string()
        self.patch(
            maasserver.models.config, "DEFAULT_CONFIG",
            {name: {'key': 'value'}})
        config = Config.objects.get_config(name)
        config.update({'key2': 'value2'})

        self.assertEqual({'key': 'value'}, Config.objects.get_config(name))

    def test_manager_set_config_creates_config(self):
        Config.objects.set_config('name', 'config1')
        Config.objects.set_config('name', 'config2')
        self.assertSequenceEqual(
            ['config2'],
            [config.value for config in Config.objects.filter(name='name')])

    def test_manager_config_changed_connect_connects(self):
        recorder = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.set_config(name, value)
        config = Config.objects.get(name=name)

        self.assertEqual(1, len(recorder.calls))
        self.assertEqual((Config, config, True), recorder.calls[0][0])

    def test_manager_config_changed_connect_connects_multiple(self):
        recorder = CallRecorder()
        recorder2 = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.config_changed_connect(name, recorder2)
        Config.objects.set_config(name, value)

        self.assertEqual(1, len(recorder.calls))
        self.assertEqual(1, len(recorder2.calls))

    def test_manager_config_changed_connect_connects_multiple_same(self):
        # If the same method is connected twice, it will only get called
        # once.
        recorder = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.config_changed_connect(name, recorder)
        Config.objects.set_config(name, value)

        self.assertEqual(1, len(recorder.calls))

    def test_manager_config_changed_connect_connects_by_config_name(self):
        recorder = CallRecorder()
        name = factory.make_string()
        value = factory.make_string()
        Config.objects.config_changed_connect(name, recorder)
        another_name = factory.make_string()
        Config.objects.set_config(another_name, value)

        self.assertEqual(0, len(recorder.calls))

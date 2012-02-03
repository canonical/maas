# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Tests for the fake Cobbler API."""

__metaclass__ = type
__all__ = []

from itertools import count
from random import randint
from tempfile import NamedTemporaryFile
import xmlrpclib

from provisioningserver.cobblerclient import (
    CobblerDistro,
    CobblerImage,
    CobblerPreseeds,
    CobblerProfile,
    CobblerRepo,
    CobblerSession,
    CobblerSystem,
    )
from provisioningserver.testing.fakecobbler import (
    FakeCobbler,
    FakeTwistedProxy,
    )
from testtools.content import text_content
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.testcase import (
    ExpectedException,
    TestCase,
    )
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )


unique_ints = count(randint(0, 9999))


class FakeCobblerSession(CobblerSession):
    """A `CobblerSession` instrumented not to use real XMLRPC."""

    def __init__(self, url, user, password, fake_cobbler=None):
        self.fake_proxy = FakeTwistedProxy(fake_cobbler=fake_cobbler)
        super(FakeCobblerSession, self).__init__(url, user, password)

    def _make_twisted_proxy(self):
        return self.fake_proxy

    def _login(self):
        self.token = self.proxy.fake_cobbler.login(self.user, self.password)


@inlineCallbacks
def fake_cobbler_session(url=None, user=None, password=None,
                         fake_cobbler=None):
    """Fake a `CobblerSession`."""
    unique_number = next(unique_ints)
    if user is None:
        user = "user%d" % unique_number
    if password is None:
        password = "password%d" % unique_number
    if fake_cobbler is None:
        fake_cobbler = FakeCobbler(passwords={user: password})
    session = FakeCobblerSession(
        url, user, password, fake_cobbler=fake_cobbler)
    yield session._authenticate()
    returnValue(session)


def make_file():
    """Make a temporary file."""
    temp_file = NamedTemporaryFile()
    temp_file.write("Data here.")
    temp_file.flush()
    return temp_file


def default_to_file(attributes, attribute, required_attrs):
    """If `attributes[attribute]` is required but not set, make a file.

    :return: A temporary file.  Keep this alive as long as you need the file.
    """
    if attribute in required_attrs and attribute not in attributes:
        temp_file = make_file()
        attributes[attribute] = temp_file.name
        return temp_file
    else:
        return None


@inlineCallbacks
def default_to_object(attributes, attribute, required_attrs, session,
                      cobbler_class):
    """If `attributes[attribute]` is required but not set, make an object."""
    if attribute in required_attrs and attribute not in attributes:
        other_obj = yield fake_cobbler_object(session, cobbler_class)
        attributes[attribute] = other_obj.name


@inlineCallbacks
def fake_cobbler_object(session, object_class, name=None, attributes=None):
    """Create a fake Cobbler object.

    :param session: `CobblerSession`.
    :param object_class: concrete `CobblerObject` class to instantiate.
    :param name: Option name for the object.
    :param attributes: Optional dict of attribute values for the object.
    """
    if attributes is None:
        attributes = {}
    else:
        attributes = attributes.copy()
    unique_int = next(unique_ints)
    if name is None:
        name = 'name-%s-%d' % (object_class.object_type, unique_int)
    attributes['name'] = name
    temp_files = [
        default_to_file(
            attributes, 'kernel', object_class.required_attributes),
        default_to_file(
            attributes, 'initrd', object_class.required_attributes),
        ]
    yield default_to_object(
        attributes, 'profile', object_class.required_attributes, session,
        CobblerProfile)
    yield default_to_object(
        attributes, 'distro', object_class.required_attributes, session,
        CobblerDistro)
    for attr in object_class.required_attributes:
        if attr not in attributes:
            attributes[attr] = '%s-%d' % (attr, unique_int)
    new_object = yield object_class.new(session, name, attributes)
    # Keep the temporary files alive for the lifetime of the object.
    new_object._hold_these_files_please = temp_files
    returnValue(new_object)


class TestFakeCobbler(TestCase):
    """Test `FakeCobbler`.

    These tests should also pass if run against a real (clean) Cobbler.
    """
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def test_login_failure_raises_failure(self):
        cobbler = FakeCobbler(passwords={'moi': 'potahto'})
        with ExpectedException(xmlrpclib.Fault):
            return_value = yield fake_cobbler_session(
                user='moi', password='potayto', fake_cobbler=cobbler)
            self.addDetail('return_value', text_content(repr(return_value)))

    @inlineCallbacks
    def test_expired_token_triggers_retry(self):
        session = yield fake_cobbler_session()
        # When an auth token expires, the server just forgets about it.
        old_token = session.token
        session.fake_proxy.fake_cobbler.fake_retire_token(old_token)

        # Use of the token will now fail with an "invalid token"
        # error.  The Cobbler client notices this, re-authenticates, and
        # re-runs the method.
        yield fake_cobbler_object(session, CobblerRepo)

        # The re-authentication results in a fresh token.
        self.assertNotEqual(old_token, session.token)

    @inlineCallbacks
    def test_valid_token_does_not_raise_auth_error(self):
        session = yield fake_cobbler_session()
        old_token = session.token
        yield fake_cobbler_object(session, CobblerRepo)
        self.assertEqual(old_token, session.token)


class CobblerObjectTestScenario:
    """Generic tests for the various `CobblerObject` classes.

    This will be run once for each of the classes in the hierarchy.
    """

    # The class to test
    cobbler_class = None

    def make_name(self):
        return "name-%s-%d" % (
            self.cobbler_class.object_type,
            next(unique_ints),
            )

    def test_normalize_attribute_passes_on_simple_attribute_name(self):
        self.assertEqual(
            'name', self.cobbler_class._normalize_attribute('name'))

    def test_normalize_attribute_rejects_unknown_attribute(self):
        self.assertRaises(
            AssertionError,
            self.cobbler_class._normalize_attribute, 'some-unknown-attribute')

    @inlineCallbacks
    def test_create_object(self):
        session = yield fake_cobbler_session()
        name = self.make_name()
        obj = yield fake_cobbler_object(session, self.cobbler_class, name)
        self.assertEqual(name, obj.name)

    @inlineCallbacks
    def test_create_object_fails_if_cobbler_returns_False(self):

        def return_false(*args):
            return False

        session = yield fake_cobbler_session()
        session.fake_proxy.fake_cobbler.xapi_object_edit = return_false
        with ExpectedException(RuntimeError):
            yield fake_cobbler_object(session, self.cobbler_class)

    @inlineCallbacks
    def test_find_returns_empty_list_if_no_match(self):
        session = yield fake_cobbler_session()
        name = self.make_name()
        matches = yield self.cobbler_class.find(session, name=name)
        self.assertSequenceEqual([], matches)

    @inlineCallbacks
    def test_find_matches_name(self):
        session = yield fake_cobbler_session()
        name = self.make_name()
        yield fake_cobbler_object(session, self.cobbler_class, name)
        by_name = yield self.cobbler_class.find(session, name=name)
        self.assertSequenceEqual([name], [obj.name for obj in by_name])

    @inlineCallbacks
    def test_find_matches_attribute(self):
        session = yield fake_cobbler_session()
        name = self.make_name()
        comment = "This is comment #%d" % next(unique_ints)
        yield fake_cobbler_object(
            session, self.cobbler_class, name, {'comment': comment})
        by_comment = yield self.cobbler_class.find(session, comment=comment)
        self.assertSequenceEqual([name], [obj.name for obj in by_comment])

    @inlineCallbacks
    def test_find_without_args_finds_everything(self):
        session = yield fake_cobbler_session()
        name = self.make_name()
        yield fake_cobbler_object(session, self.cobbler_class, name)
        found_objects = yield self.cobbler_class.find(session)
        self.assertIn(name, [obj.name for obj in found_objects])

    @inlineCallbacks
    def test_get_object_retrieves_attributes(self):
        session = yield fake_cobbler_session()
        comment = "This is comment #%d" % next(unique_ints)
        name = self.make_name()
        obj = yield fake_cobbler_object(
            session, self.cobbler_class, name, {'comment': comment})
        attributes = yield obj.get_values()
        self.assertEqual(name, attributes['name'])
        self.assertEqual(comment, attributes['comment'])

    @inlineCallbacks
    def test_get_objects_retrieves_attributes_for_all_objects(self):
        session = yield fake_cobbler_session()
        comment = "This is comment #%d" % next(unique_ints)
        name = self.make_name()
        yield fake_cobbler_object(
            session, self.cobbler_class, name, {'comment': comment})
        all_objects = yield self.cobbler_class.get_all_values(session)
        found_obj = all_objects[name]
        self.assertEqual(name, found_obj['name'])
        self.assertEqual(comment, found_obj['comment'])

    @inlineCallbacks
    def test_get_handle_finds_handle(self):
        session = yield fake_cobbler_session()
        name = self.make_name()
        obj = yield fake_cobbler_object(session, self.cobbler_class, name)
        handle = yield obj._get_handle()
        self.assertNotEqual(None, handle)

    @inlineCallbacks
    def test_get_handle_distinguishes_objects(self):
        session = yield fake_cobbler_session()
        obj1 = yield fake_cobbler_object(session, self.cobbler_class)
        handle1 = yield obj1._get_handle()
        obj2 = yield fake_cobbler_object(session, self.cobbler_class)
        handle2 = yield obj2._get_handle()
        self.assertNotEqual(handle1, handle2)

    @inlineCallbacks
    def test_get_handle_is_consistent(self):
        session = yield fake_cobbler_session()
        obj = yield fake_cobbler_object(session, self.cobbler_class)
        handle1 = yield obj._get_handle()
        handle2 = yield obj._get_handle()
        self.assertEqual(handle1, handle2)

    @inlineCallbacks
    def test_delete_removes_object(self):
        session = yield fake_cobbler_session()
        name = self.make_name()
        obj = yield fake_cobbler_object(session, self.cobbler_class, name)
        yield obj.delete()
        matches = yield self.cobbler_class.find(session, name=name)
        self.assertSequenceEqual([], matches)


class TestCobblerDistro(CobblerObjectTestScenario, TestCase):
    """Tests for `CobblerDistro`.  Uses generic `CobblerObject` scenario."""
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)
    cobbler_class = CobblerDistro

    def test_normalize_attribute_normalizes_separators(self):
        # Based on the Cobbler source, Distro seems to use only dashes
        # as separators in attribute names.  The equivalents with
        # underscores get translated to the ones Cobbler seems to
        # expect.
        inputs = [
            'mgmt-classes',
            'mgmt_classes',
            ]
        self.assertSequenceEqual(
            ['mgmt-classes'] * 2,
            map(self.cobbler_class._normalize_attribute, inputs))


class TestCobblerImage(CobblerObjectTestScenario, TestCase):
    """Tests for `CobblerImage`.  Uses generic `CobblerObject` scenario."""
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)
    cobbler_class = CobblerImage

    def test_normalize_attribute_normalizes_separators(self):
        # Based on the Cobbler source, Image seems to use only
        # underscores as separators in attribute names.  The equivalents
        # with dashes get translated to the ones Cobbler seems to
        # expect.
        inputs = [
            'image-type',
            'image_type',
            ]
        self.assertSequenceEqual(
            ['image_type'] * 2,
            map(self.cobbler_class._normalize_attribute, inputs))


class TestCobblerProfile(CobblerObjectTestScenario, TestCase):
    """Tests for `CobblerProfile`.  Uses generic `CobblerObject` scenario."""
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)
    cobbler_class = CobblerProfile

    def test_normalize_attribute_normalizes_separators(self):
        # Based on the Cobbler source, Profile seems to use a mix of
        # underscores and dashes in attribute names.  The MaaS Cobbler
        # wrapper ignores the difference, and uses whatever Cobbler
        # seems to expect in either case.
        inputs = [
            'enable-menu',
            'enable_menu',
            'name_servers',
            'name-servers',
            ]
        expected_outputs = [
            'enable-menu',
            'enable-menu',
            'name_servers',
            'name_servers',
            ]
        self.assertSequenceEqual(
            expected_outputs,
            map(self.cobbler_class._normalize_attribute, inputs))


class TestCobblerRepo(CobblerObjectTestScenario, TestCase):
    """Tests for `CobblerRepo`.  Uses generic `CobblerObject` scenario."""
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)
    cobbler_class = CobblerRepo


class TestCobblerSystem(CobblerObjectTestScenario, TestCase):
    """Tests for `CobblerSystem`.  Uses generic `CobblerObject` scenario."""
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)
    cobbler_class = CobblerSystem

    def make_name(self):
        return 'system-%d' % next(unique_ints)

    @inlineCallbacks
    def make_systems(self, session, num_systems):
        names = [self.make_name() for counter in range(num_systems)]
        systems = []
        for name in names:
            new_system = yield fake_cobbler_object(
                session, self.cobbler_class, name)
            systems.append(new_system)
        returnValue((names, systems))

    @inlineCallbacks
    def get_handles(self, systems):
        handles = []
        for system in systems:
            handle = yield system._get_handle()
            handles.append(handle)
        returnValue(handles)

    @inlineCallbacks
    def test_powerOnMultiple(self):
        session = yield fake_cobbler_session()
        names, systems = yield self.make_systems(session, 3)
        handles = yield self.get_handles(systems)
        yield self.cobbler_class.powerOnMultiple(session, names[:2])
        self.assertEqual(
            dict((handle, 'on') for handle in handles[:2]),
            session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_powerOffMultiple(self):
        session = yield fake_cobbler_session()
        names, systems = yield self.make_systems(session, 3)
        handles = yield self.get_handles(systems)
        yield self.cobbler_class.powerOffMultiple(session, names[:2])
        self.assertEqual(
            dict((handle, 'off') for handle in handles[:2]),
            session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_rebootMultiple(self):
        session = yield fake_cobbler_session()
        names, systems = yield self.make_systems(session, 3)
        handles = yield self.get_handles(systems)
        yield self.cobbler_class.rebootMultiple(session, names[:2])
        self.assertEqual(
            dict((handle, 'reboot') for handle in handles[:2]),
            session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_powerOn(self):
        session = yield fake_cobbler_session()
        names, systems = yield self.make_systems(session, 2)
        handle = yield systems[0]._get_handle()
        yield systems[0].powerOn()
        self.assertEqual(
            {handle: 'on'}, session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_powerOff(self):
        session = yield fake_cobbler_session()
        names, systems = yield self.make_systems(session, 2)
        handle = yield systems[0]._get_handle()
        yield systems[0].powerOff()
        self.assertEqual(
            {handle: 'off'}, session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_reboot(self):
        session = yield fake_cobbler_session()
        names, systems = yield self.make_systems(session, 2)
        handle = yield systems[0]._get_handle()
        yield systems[0].reboot()
        self.assertEqual(
            {handle: 'reboot'}, session.fake_proxy.fake_cobbler.system_power)


class TestCobblerPreseeds(TestCase):
    """Tests for `CobblerPreseeds`."""
    # Use a longer timeout so that we can run these tests against a real
    # Cobbler.
    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    @inlineCallbacks
    def make_preseeds_api(self):
        session = yield fake_cobbler_session()
        returnValue(CobblerPreseeds(session))

    @inlineCallbacks
    def test_can_read_and_write_template(self):
        preseeds = yield self.make_preseeds_api()
        unique_int = next(unique_ints)
        path = '/var/lib/cobbler/kickstarts/template-%d' % unique_int
        text = "Template text #%d" % unique_int
        yield preseeds.write_template(path, text)
        contents = yield preseeds.read_template(path)
        self.assertEqual(text, contents)

    @inlineCallbacks
    def test_can_read_and_write_snippets(self):
        preseeds = yield self.make_preseeds_api()
        unique_int = next(unique_ints)
        path = '/var/lib/cobbler/snippets/snippet-%d' % unique_int
        text = "Snippet text #%d" % unique_int
        yield preseeds.write_snippet(path, text)
        contents = yield preseeds.read_snippet(path)
        self.assertEqual(text, contents)

    @inlineCallbacks
    def test_get_templates_lists_templates(self):
        preseeds = yield self.make_preseeds_api()
        unique_int = next(unique_ints)
        path = '/var/lib/cobbler/kickstarts/template-%d' % unique_int
        yield preseeds.write_template(path, "Text")
        templates = yield preseeds.get_templates()
        self.assertIn(path, templates)

    @inlineCallbacks
    def test_get_snippets_lists_snippets(self):
        preseeds = yield self.make_preseeds_api()
        unique_int = next(unique_ints)
        path = '/var/lib/cobbler/snippets/snippet-%d' % unique_int
        yield preseeds.write_snippet(path, "Text")
        snippets = yield preseeds.get_snippets()
        self.assertIn(path, snippets)

    @inlineCallbacks
    def test_templates_do_not_show_up_as_snippets(self):
        preseeds = yield self.make_preseeds_api()
        unique_int = next(unique_ints)
        path = '/var/lib/cobbler/kickstarts/template-%d' % unique_int
        yield preseeds.write_template(path, "Text")
        snippets = yield preseeds.get_snippets()
        self.assertNotIn(path, snippets)

    @inlineCallbacks
    def test_snippets_do_not_show_up_as_templates(self):
        preseeds = yield self.make_preseeds_api()
        unique_int = next(unique_ints)
        path = '/var/lib/cobbler/snippets/snippet-%d' % unique_int
        yield preseeds.write_snippet(path, "Text")
        templates = yield preseeds.get_templates()
        self.assertNotIn(path, templates)

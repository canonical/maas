# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.cobblerclient`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from itertools import count
from random import randint

from maastesting.testcase import TestCase
from provisioningserver.cobblerclient import (
    CobblerDistro,
    CobblerImage,
    CobblerPreseeds,
    CobblerProfile,
    CobblerRepo,
    CobblerSystem,
    CobblerXMLRPCProxy,
    tilde_to_None,
    )
from provisioningserver.testing.factory import CobblerFakeFactory
from provisioningserver.testing.fakecobbler import log_in_to_fake_cobbler
from testtools.deferredruntest import AsynchronousDeferredRunTest
from testtools.testcase import ExpectedException
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.test.proto_helpers import MemoryReactor


class TestRepairingCobblerResponses(TestCase):
    """See `tilde_to_None`."""

    def test_tilde_to_None(self):
        self.assertIsNone(tilde_to_None("~"))

    def test_tilde_to_None_list(self):
        self.assertEqual(
            [1, 2, 3, None, 5],
            tilde_to_None([1, 2, 3, "~", 5]))

    def test_tilde_to_None_nested_list(self):
        self.assertEqual(
            [1, 2, [3, None], 5],
            tilde_to_None([1, 2, [3, "~"], 5]))

    def test_tilde_to_None_dict(self):
        self.assertEqual(
            {"one": 1, "two": None},
            tilde_to_None({"one": 1, "two": "~"}))

    def test_tilde_to_None_nested_dict(self):
        self.assertEqual(
            {"one": 1, "two": {"three": None}},
            tilde_to_None({"one": 1, "two": {"three": "~"}}))

    def test_tilde_to_None_nested_mixed(self):
        self.assertEqual(
            {"one": 1, "two": [3, 4, None]},
            tilde_to_None({"one": 1, "two": [3, 4, "~"]}))

    def test_CobblerXMLRPCProxy(self):
        reactor = MemoryReactor()
        proxy = CobblerXMLRPCProxy(
            "http://localhost:1234/nowhere", reactor=reactor)
        d = proxy.callRemote("cobble", 1, 2, 3)
        # A connection has been initiated.
        self.assertEqual(1, len(reactor.tcpClients))
        [client] = reactor.tcpClients
        self.assertEqual("localhost", client[0])
        self.assertEqual(1234, client[1])
        # A "broken" response from Cobbler is "repaired".
        d.callback([1, 2, "~"])
        self.assertEqual([1, 2, None], d.result)


unique_ints = count(randint(0, 9999))


class CobblerObjectTestScenario(CobblerFakeFactory):
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

    def test_normalize_attribute_alternative_attributes(self):
        # _normalize_attribute() can be passed a different set of attributes
        # against which to normalize.
        allowed_attributes = set(["some-unknown-attribute"])
        self.assertEqual(
            'some-unknown-attribute',
            self.cobbler_class._normalize_attribute(
                'some-unknown-attribute', allowed_attributes))

    @inlineCallbacks
    def test_create_object(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        obj = yield self.fake_cobbler_object(
            session, self.cobbler_class, name)
        self.assertEqual(name, obj.name)

    @inlineCallbacks
    def test_create_object_fails_if_cobbler_returns_False(self):

        def return_false(*args):
            return False

        session = yield log_in_to_fake_cobbler()
        session.fake_proxy.fake_cobbler.xapi_object_edit = return_false
        with ExpectedException(RuntimeError):
            yield self.fake_cobbler_object(session, self.cobbler_class)

    @inlineCallbacks
    def test_find_returns_empty_list_if_no_match(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        matches = yield self.cobbler_class.find(session, name=name)
        self.assertSequenceEqual([], matches)

    @inlineCallbacks
    def test_find_matches_name(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        yield self.fake_cobbler_object(session, self.cobbler_class, name)
        by_name = yield self.cobbler_class.find(session, name=name)
        self.assertSequenceEqual([name], [obj.name for obj in by_name])

    @inlineCallbacks
    def test_find_matches_attribute(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        comment = "This is comment #%d" % next(unique_ints)
        yield self.fake_cobbler_object(
            session, self.cobbler_class, name, {'comment': comment})
        by_comment = yield self.cobbler_class.find(session, comment=comment)
        self.assertSequenceEqual([name], [obj.name for obj in by_comment])

    @inlineCallbacks
    def test_find_without_args_finds_everything(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        yield self.fake_cobbler_object(session, self.cobbler_class, name)
        found_objects = yield self.cobbler_class.find(session)
        self.assertIn(name, [obj.name for obj in found_objects])

    @inlineCallbacks
    def test_get_object_retrieves_attributes(self):
        session = yield log_in_to_fake_cobbler()
        comment = "This is comment #%d" % next(unique_ints)
        name = self.make_name()
        obj = yield self.fake_cobbler_object(
            session, self.cobbler_class, name, {'comment': comment})
        attributes = yield obj.get_values()
        self.assertEqual(name, attributes['name'])
        self.assertEqual(comment, attributes['comment'])

    @inlineCallbacks
    def test_get_objects_retrieves_attributes_for_all_objects(self):
        session = yield log_in_to_fake_cobbler()
        comment = "This is comment #%d" % next(unique_ints)
        name = self.make_name()
        yield self.fake_cobbler_object(
            session, self.cobbler_class, name, {'comment': comment})
        all_objects = yield self.cobbler_class.get_all_values(session)
        found_obj = all_objects[name]
        self.assertEqual(name, found_obj['name'])
        self.assertEqual(comment, found_obj['comment'])

    @inlineCallbacks
    def test_get_values_returns_None_for_non_existent_object(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        values = yield self.cobbler_class(session, name).get_values()
        self.assertIsNone(values)

    @inlineCallbacks
    def test_get_handle_finds_handle(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        obj = yield self.fake_cobbler_object(
            session, self.cobbler_class, name)
        handle = yield obj._get_handle()
        self.assertNotEqual(None, handle)

    @inlineCallbacks
    def test_get_handle_distinguishes_objects(self):
        session = yield log_in_to_fake_cobbler()
        obj1 = yield self.fake_cobbler_object(session, self.cobbler_class)
        handle1 = yield obj1._get_handle()
        obj2 = yield self.fake_cobbler_object(session, self.cobbler_class)
        handle2 = yield obj2._get_handle()
        self.assertNotEqual(handle1, handle2)

    @inlineCallbacks
    def test_get_handle_is_consistent(self):
        session = yield log_in_to_fake_cobbler()
        obj = yield self.fake_cobbler_object(session, self.cobbler_class)
        handle1 = yield obj._get_handle()
        handle2 = yield obj._get_handle()
        self.assertEqual(handle1, handle2)

    @inlineCallbacks
    def test_delete_removes_object(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        obj = yield self.fake_cobbler_object(
            session, self.cobbler_class, name)
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
        # underscores and dashes in attribute names.  The MAAS Cobbler
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
            new_system = yield self.fake_cobbler_object(
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
    def test_interface_set_mac_address(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        obj = yield self.fake_cobbler_object(
            session, self.cobbler_class, name)
        yield obj.modify(
            {"interface": "eth0", "mac_address": "12:34:56:78:90:12"})
        state = yield obj.get_values()
        interfaces = state.get("interfaces", {})
        self.assertEqual(["eth0"], sorted(interfaces))
        state_eth0 = interfaces["eth0"]
        self.assertEqual("12:34:56:78:90:12", state_eth0["mac_address"])

    @inlineCallbacks
    def test_interface_set_dns_name(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        obj = yield self.fake_cobbler_object(
            session, self.cobbler_class, name)
        yield obj.modify(
            {"interface": "eth0", "dns_name": "epitaph"})
        state = yield obj.get_values()
        interfaces = state.get("interfaces", {})
        self.assertEqual(["eth0"], sorted(interfaces))
        state_eth0 = interfaces["eth0"]
        self.assertEqual("epitaph", state_eth0["dns_name"])

    @inlineCallbacks
    def test_interface_delete_interface(self):
        session = yield log_in_to_fake_cobbler()
        name = self.make_name()
        obj = yield self.fake_cobbler_object(
            session, self.cobbler_class, name)
        yield obj.modify(
            {"interface": "eth0", "mac_address": "12:34:56:78:90:12"})
        yield obj.modify(
            {"interface": "eth0", "delete_interface": "ignored"})
        state = yield obj.get_values()
        interfaces = state.get("interfaces", {})
        self.assertEqual([], sorted(interfaces))

    @inlineCallbacks
    def test_powerOnMultiple(self):
        session = yield log_in_to_fake_cobbler()
        names, systems = yield self.make_systems(session, 3)
        handles = yield self.get_handles(systems)
        yield self.cobbler_class.powerOnMultiple(session, names[:2])
        self.assertEqual(
            dict((handle, 'on') for handle in handles[:2]),
            session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_powerOffMultiple(self):
        session = yield log_in_to_fake_cobbler()
        names, systems = yield self.make_systems(session, 3)
        handles = yield self.get_handles(systems)
        yield self.cobbler_class.powerOffMultiple(session, names[:2])
        self.assertEqual(
            dict((handle, 'off') for handle in handles[:2]),
            session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_rebootMultiple(self):
        session = yield log_in_to_fake_cobbler()
        names, systems = yield self.make_systems(session, 3)
        handles = yield self.get_handles(systems)
        yield self.cobbler_class.rebootMultiple(session, names[:2])
        self.assertEqual(
            dict((handle, 'reboot') for handle in handles[:2]),
            session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_powerOn(self):
        session = yield log_in_to_fake_cobbler()
        names, systems = yield self.make_systems(session, 2)
        handle = yield systems[0]._get_handle()
        yield systems[0].powerOn()
        self.assertEqual(
            {handle: 'on'}, session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_powerOff(self):
        session = yield log_in_to_fake_cobbler()
        names, systems = yield self.make_systems(session, 2)
        handle = yield systems[0]._get_handle()
        yield systems[0].powerOff()
        self.assertEqual(
            {handle: 'off'}, session.fake_proxy.fake_cobbler.system_power)

    @inlineCallbacks
    def test_reboot(self):
        session = yield log_in_to_fake_cobbler()
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
        session = yield log_in_to_fake_cobbler()
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

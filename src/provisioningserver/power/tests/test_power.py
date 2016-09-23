# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~provisioningserver.power`."""

__all__ = []

from operator import methodcaller
import random
import re
from unittest.mock import ANY

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.runtest import MAASTwistedRunTest
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result
from provisioningserver import power
from provisioningserver.rpc import region
from provisioningserver.rpc.testing import MockClusterToRegionRPCFixture
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    Is,
    MatchesAll,
    MatchesDict,
    Not,
)


class TestPowerHelpers(MAASTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def patch_rpc_methods(self):
        fixture = self.useFixture(MockClusterToRegionRPCFixture())
        protocol, io = fixture.makeEventLoop(
            region.MarkNodeFailed, region.UpdateNodePowerState,
            region.SendEvent)
        return protocol, io

    def test_power_state_update_calls_UpdateNodePowerState(self):
        system_id = factory.make_name('system_id')
        state = random.choice(['on', 'off'])
        protocol, io = self.patch_rpc_methods()
        d = power.power_state_update(system_id, state)
        # This blocks until the deferred is complete
        io.flush()
        self.expectThat(extract_result(d), Equals({}))
        self.assertThat(
            protocol.UpdateNodePowerState,
            MockCalledOnceWith(
                ANY,
                system_id=system_id,
                power_state=state)
        )


class TestIpExtractor(MAASTestCase):

    scenarios = (
        ("no-name", {
            'val': 'http://:555/path',
            'expected': {
                'password': None, 'port': '555', 'path': '/path',
                'query': None, 'address': '', 'user': None,
                'schema': 'http'}}),
        ("name-with-brackets", {
            'val': 'http://[localhost]/path',
            'expected': None}),
        ("ipv4-with-brackets", {
            'val': 'http://[127.0.0.1]/path',
            'expected': None}),
        ("ipv4-with-leading-bracket", {
            'val': 'http://[127.0.0.1/path',
            'expected': None}),
        ("ipv4-with-trailing-bracket", {
            'val': 'http://127.0.0.1]/path',
            'expected': None}),
        ("ipv6-no-brackets", {
            'val': 'http://2001:db8::1/path',
            'expected': None}),
        ("name", {
            'val': 'http://localhost:555/path',
            'expected': {
                'password': None, 'port': '555', 'path': '/path',
                'query': None, 'address': 'localhost', 'user': None,
                'schema': 'http'}}),
        ("ipv4", {
            'val': 'http://127.0.0.1:555/path',
            'expected': {
                'password': None, 'port': '555', 'path': '/path',
                'query': None, 'address': '127.0.0.1', 'user': None,
                'schema': 'http'}}),
        ("ipv6-formatted-ipv4", {
            'val': 'http://[::ffff:127.0.0.1]:555/path',
            'expected': {
                'password': None, 'port': '555', 'path': '/path',
                'query': None, 'address': '::ffff:127.0.0.1', 'user': None,
                'schema': 'http'}}),
        ("ipv6", {
            'val': 'http://[2001:db8::1]:555/path',
            'expected': {
                'password': None, 'port': '555', 'path': '/path',
                'query': None, 'address': '2001:db8::1', 'user': None,
                'schema': 'http'}}),
        ("ipv4-no-slash", {
            'val': 'http://127.0.0.1',
            'expected': {
                'password': None, 'port': None, 'path': None,
                'query': None, 'address': '127.0.0.1', 'user': None,
                'schema': 'http'}}),
        ("name-no-slash", {
            'val': 'http://localhost',
            'expected': {
                'password': None, 'port': None, 'path': None,
                'query': None, 'address': 'localhost', 'user': None,
                'schema': 'http'}}),
        ("ipv6-no-slash", {
            'val': 'http://[2001:db8::1]',
            'expected': {
                'password': None, 'port': None, 'path': None,
                'query': None, 'address': '2001:db8::1', 'user': None,
                'schema': 'http'}}),
        ("ipv4-no-port", {
            'val': 'http://127.0.0.1/path',
            'expected': {
                'password': None, 'port': None, 'path': '/path',
                'query': None, 'address': '127.0.0.1', 'user': None,
                'schema': 'http'}}),
        ("name-no-port", {
            'val': 'http://localhost/path',
            'expected': {
                'password': None, 'port': None, 'path': '/path',
                'query': None, 'address': 'localhost', 'user': None,
                'schema': 'http'}}),
        ("ipv6-no-port", {
            'val': 'http://[2001:db8::1]/path',
            'expected': {
                'password': None, 'port': None, 'path': '/path',
                'query': None, 'address': '2001:db8::1', 'user': None,
                'schema': 'http'}}),
        ("user-pass-ipv4", {
            'val': 'http://user:pass@127.0.0.1:555/path',
            'expected': {
                'password': 'pass', 'port': '555', 'path': '/path',
                'query': None, 'address': '127.0.0.1', 'user': 'user',
                'schema': 'http'}}),
        ("user-pass-ipv6", {
            'val': 'http://user:pass@[2001:db8::1]:555/path',
            'expected': {
                'password': 'pass', 'port': '555', 'path': '/path',
                'query': None, 'address': '2001:db8::1', 'user': 'user',
                'schema': 'http'}}),
        ("user-pass-ipv4-no-port", {
            'val': 'http://user:pass@127.0.0.1/path',
            'expected': {
                'password': 'pass', 'port': None, 'path': '/path',
                'query': None, 'address': '127.0.0.1', 'user': 'user',
                'schema': 'http'}}),
        ("user-pass-ipv6-no-port", {
            'val': 'http://user:pass@[2001:db8::1]/path',
            'expected': {
                'password': 'pass', 'port': None, 'path': '/path',
                'query': None, 'address': '2001:db8::1', 'user': 'user',
                'schema': 'http'}}),
    )

    def get_expected_matcher(self):
        if self.expected is None:
            return Is(None)
        else:
            expected = {
                key: Equals(value)
                for key, value in self.expected.items()
            }
            return MatchesAll(
                Not(Is(None)),
                AfterPreprocessing(
                    methodcaller("groupdict"),
                    MatchesDict(expected),
                    annotate=False,
                ),
                first_only=True,
            )

    def test_make_ip_extractor(self):
        actual = re.match(power.schema.IP_EXTRACTOR_PATTERNS.URL, self.val)
        self.assertThat(actual, self.get_expected_matcher())

# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test MAAS HTTP API client."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from email.parser import Parser
from random import randint
from urlparse import (
    parse_qs,
    urljoin,
    urlparse,
    )

from apiclient.maas_client import (
    _ascii_url,
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
from maastesting.factory import factory
from maastesting.testcase import TestCase


class TestHelpers(TestCase):

    def test_ascii_url_leaves_ascii_bytes_unchanged(self):
        self.assertEqual(
            b'http://example.com/', _ascii_url(b'http://example.com/'))
        self.assertIsInstance(_ascii_url(b'http://example.com'), bytes)

    def test_ascii_url_asciifies_unicode(self):
        self.assertEqual(
            b'http://example.com/', _ascii_url('http://example.com/'))
        self.assertIsInstance(_ascii_url('http://example.com'), bytes)


class TestMAASOAuth(TestCase):

    def test_sign_request_adds_header(self):
        headers = {}
        auth = MAASOAuth('consumer_key', 'resource_token', 'resource_secret')
        auth.sign_request('http://example.com/', headers)
        self.assertIn('Authorization', headers)


class TestMAASDispatcher(TestCase):

    def test_dispatch_query_makes_direct_call(self):
        contents = factory.getRandomString()
        url = "file://%s" % self.make_file(contents=contents)
        self.assertEqual(
            contents, MAASDispatcher().dispatch_query(url, {}).read())


def make_url():
    """Create an arbitrary URL."""
    return 'http://example.com:%d/%s/' % (
        factory.getRandomPort(),
        factory.getRandomString(),
        )


def make_path():
    """Create an arbitrary resource path."""
    return "/" + '/'.join(factory.getRandomString() for counter in range(2))


class FakeDispatcher:
    """Fake MAASDispatcher.  Records last invocation, returns given result."""

    last_call = None

    def __init__(self, result=None):
        self.result = result

    def dispatch_query(self, request_url, headers, method=None, data=None):
        self.last_call = {
            'request_url': request_url,
            'headers': headers,
            'method': method,
            'data': data,
        }
        return self.result


def make_client(root=None, result=None):
    """Create a MAASClient."""
    if root is None:
        root = make_url()
    auth = MAASOAuth(
        factory.getRandomString(), factory.getRandomString(),
        factory.getRandomString())
    return MAASClient(auth, FakeDispatcher(result=result), root)


class TestMAASClient(TestCase):

    def test_make_url_joins_root_and_path(self):
        path = make_path()
        client = make_client()
        expected = client.url.rstrip("/") + "/" + path.lstrip("/")
        self.assertEqual(expected, client._make_url(path))

    def test_make_url_converts_sequence_to_path(self):
        path = ['top', 'sub', 'leaf']
        client = make_client(root='http://example.com/')
        self.assertEqual(
            'http://example.com/top/sub/leaf', client._make_url(path))

    def test_make_url_represents_path_components_as_text(self):
        number = randint(0, 100)
        client = make_client()
        self.assertEqual(
            urljoin(client.url, unicode(number)), client._make_url([number]))

    def test_formulate_get_makes_url(self):
        path = make_path()
        client = make_client()
        url, headers = client._formulate_get(path)
        expected = client.url.rstrip("/") + "/" + path.lstrip("/")
        self.assertEqual(expected, url)

    def test_formulate_get_adds_parameters_to_url(self):
        params = {
            factory.getRandomString(): factory.getRandomString()
            for counter in range(3)}
        url, headers = make_client()._formulate_get(make_path(), params)
        expectation = {key: [value] for key, value in params.items()}
        self.assertEqual(expectation, parse_qs(urlparse(url).query))

    def test_formulate_get_signs_request(self):
        url, headers = make_client()._formulate_get(make_path())
        self.assertIn('Authorization', headers)

    def test_formulate_change_makes_url(self):
        path = make_path()
        client = make_client()
        url, headers, body = client._formulate_change(path, {})
        expected = client.url.rstrip("/") + "/" + path.lstrip("/")
        self.assertEqual(expected, url)

    def test_formulate_change_signs_request(self):
        url, headers, body = make_client()._formulate_change(make_path(), {})
        self.assertIn('Authorization', headers)

    def test_formulate_change_passes_parameters_in_body(self):
        params = {factory.getRandomString(): factory.getRandomString()}
        url, headers, body = make_client()._formulate_change(
            make_path(), params)
        body = Parser().parsestr(body).get_payload()
        self.assertIn('name="%s"' % params.keys()[0], body)
        self.assertIn('\r\n%s\r\n' % params.values()[0], body)

    def test_get_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        client.get(path)
        request = client.dispatcher.last_call
        self.assertEqual(client._make_url(path), request['request_url'])
        self.assertIn('Authorization', request['headers'])
        self.assertEqual('GET', request['method'])
        self.assertIsNone(request['data'])

    def test_get_without_op_gets_simple_resource(self):
        expected_result = factory.getRandomString()
        client = make_client(result=expected_result)
        result = client.get(make_path())
        self.assertEqual(expected_result, result)

    def test_get_with_op_queries_resource(self):
        path = make_path()
        method = factory.getRandomString()
        client = make_client()
        client.get(path, method)
        dispatch = client.dispatcher.last_call
        self.assertEqual(
            client._make_url(path) + '?op=%s' % method,
            dispatch['request_url'])

    def test_get_passes_parameters(self):
        path = make_path()
        param = factory.getRandomString()
        method = factory.getRandomString()
        client = make_client()
        client.get(path, method, parameter=param)
        request = client.dispatcher.last_call
        self.assertIsNone(request['data'])
        query = parse_qs(urlparse(request['request_url']).query)
        self.assertItemsEqual([param], query['parameter'])

    def test_post_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        client.post(path, factory.getRandomString())
        request = client.dispatcher.last_call
        self.assertEqual(client._make_url(path), request['request_url'])
        self.assertIn('Authorization', request['headers'])
        self.assertEqual('POST', request['method'])

    def test_post_passes_parameters(self):
        param = factory.getRandomString()
        method = factory.getRandomString()
        client = make_client()
        client.post(make_path(), method, parameter=param)
        request = client.dispatcher.last_call
        body = Parser().parsestr(request['data']).get_payload()
        self.assertIn('name="op"', body)
        self.assertIn('\r\n%s\r\n' % method, body)
        self.assertIn('name="parameter"', body)
        self.assertIn('\r\n%s\r\n' % param, body)

    def test_put_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        client.put(path, parameter=factory.getRandomString())
        request = client.dispatcher.last_call
        self.assertEqual(client._make_url(path), request['request_url'])
        self.assertIn('Authorization', request['headers'])
        self.assertEqual('PUT', request['method'])

    def test_delete_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        client.delete(path)
        request = client.dispatcher.last_call
        self.assertEqual(client._make_url(path), request['request_url'])
        self.assertIn('Authorization', request['headers'])
        self.assertEqual('DELETE', request['method'])

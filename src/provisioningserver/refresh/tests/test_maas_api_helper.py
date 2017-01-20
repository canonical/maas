# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maas_api_helper functions."""

__all__ = []

from email.utils import formatdate
from io import StringIO
import random
import re
import time
import urllib

from maastesting.factory import factory
from maastesting.matchers import (
    GreaterThanOrEqual,
    LessThanOrEqual,
    MockAnyCall,
)
from maastesting.testcase import MAASTestCase
from provisioningserver.refresh import maas_api_helper
from testtools.matchers import (
    AfterPreprocessing,
    Equals,
    MatchesAll,
    MatchesDict,
)


class TestHeaders(MAASTestCase):

    def test_oauth_headers(self):
        now = time.time()
        is_about_now = MatchesAll(
            GreaterThanOrEqual(int(now)),
            LessThanOrEqual(int(now) + 3),
        )

        url = factory.make_name("url")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        consumer_secret = factory.make_name("consumer_secret")
        headers = maas_api_helper.oauth_headers(
            url, consumer_key, token_key, token_secret, consumer_secret)
        authorization = headers['Authorization']
        self.assertRegex(authorization, '^OAuth .*')
        authorization = authorization.replace('OAuth ', '')
        oauth_arguments = {}
        for argument in authorization.split(', '):
            key, value = argument.split('=')
            oauth_arguments[key] = value.replace('"', '')

        self.assertIn('oauth_nonce', oauth_arguments)
        oauth_arguments.pop('oauth_nonce', None)

        self.assertThat(oauth_arguments, MatchesDict({
            'oauth_timestamp': AfterPreprocessing(int, is_about_now),
            'oauth_version': Equals('1.0'),
            'oauth_signature_method': Equals('PLAINTEXT'),
            'oauth_consumer_key': Equals(consumer_key),
            'oauth_token': Equals(token_key),
            'oauth_signature': Equals(
                "%s%%26%s" % (consumer_secret, token_secret)),
        }))

    def test_authenticate_headers_appends_oauth(self):
        url = factory.make_name("url")
        consumer_key = factory.make_name("consumer_key")
        token_key = factory.make_name("token_key")
        token_secret = factory.make_name("token_secret")
        consumer_secret = factory.make_name("consumer_secret")
        creds = {
            'consumer_key': consumer_key,
            'token_key': token_key,
            'token_secret': token_secret,
            'consumer_secret': consumer_secret,
        }
        headers = {}
        maas_api_helper.authenticate_headers(url, headers, creds)
        self.assertIn('Authorization', headers)

    def test_authenticate_headers_only_appends_with_consumer_key(self):
        headers = {}
        maas_api_helper.authenticate_headers(
            factory.make_name("url"), headers, {})
        self.assertEqual({}, headers)


class MAASMockHTTPHandler(urllib.request.HTTPHandler):

    def http_open(self, req):
        if 'broken_with_date' in req.get_full_url():
            code = random.choice([401, 403])
            headers = {'date': formatdate()}
        elif 'broken' in req.get_full_url():
            code = 400
            headers = {}
        else:
            code = 200
            headers = {}
        resp = urllib.request.addinfourl(
            StringIO("mock response"), headers, req.get_full_url(), code)
        resp.msg = "OK"
        return resp


class TestGetUrl(MAASTestCase):

    def setUp(self):
        super().setUp()
        opener = urllib.request.build_opener(MAASMockHTTPHandler)
        urllib.request.install_opener(opener)

    def test_geturl_sends_request(self):
        self.assertEquals(
            "mock response",
            maas_api_helper.geturl("http://%s" % factory.make_hostname(), {}))

    def test_geturl_raises_exception_on_failure(self):
        sleep = self.patch(maas_api_helper.time, 'sleep')
        warn = self.patch(maas_api_helper, 'warn')
        self.assertRaises(
            urllib.error.HTTPError,
            maas_api_helper.geturl,
            "http://%s-broken" % factory.make_hostname(),
            {})
        self.assertEquals(7, sleep.call_count)
        self.assertThat(warn, MockAnyCall('date field not in 400 headers'))

    def test_geturl_increments_skew(self):
        sleep = self.patch(maas_api_helper.time, 'sleep')
        warn = self.patch(maas_api_helper, 'warn')
        self.assertRaises(
            urllib.error.HTTPError,
            maas_api_helper.geturl,
            "http://%s-broken_with_date" % factory.make_hostname(),
            {})
        self.assertEquals(7, sleep.call_count)
        clock_shew_updates = [
            call[0][0].startswith("updated clock shew to")
            for call in warn.call_args_list
        ]
        self.assertEquals(14, len(clock_shew_updates))


class TestEncode(MAASTestCase):

    def test_encode_blank(self):
        data, headers = maas_api_helper.encode_multipart_data({}, {})
        m = re.search('boundary=([a-zA-Z]+)', headers['Content-Type'])
        boundary = m.group(1)
        self.assertEqual({
            'Content-Type': "multipart/form-data; boundary=%s" % boundary,
            'Content-Length': str(len(data)),
            }, headers)
        self.assertIsInstance(data, bytes)
        self.assertEquals("--%s--\r\n" % boundary, data.decode('utf-8'))

    def test_encode_data(self):
        key = factory.make_name('key')
        value = factory.make_name('value')
        params = {key.encode('utf-8'): value.encode('utf-8')}
        data, headers = maas_api_helper.encode_multipart_data(params, {})
        m = re.search('boundary=([a-zA-Z]+)', headers['Content-Type'])
        boundary = m.group(1)
        self.assertEqual({
            'Content-Type': "multipart/form-data; boundary=%s" % boundary,
            'Content-Length': str(len(data)),
            }, headers)
        self.assertIsInstance(data, bytes)
        self.assertEquals(
            '--%s\r\nContent-Disposition: form-data; name="%s"'
            '\r\n\r\n%s\r\n--%s--\r\n' % (boundary, key, value, boundary),
            data.decode('utf-8'))

    def test_encode_file(self):
        file = factory.make_name('file')
        content = factory.make_name('content')
        files = {file: content.encode('utf-8')}
        data, headers = maas_api_helper.encode_multipart_data({}, files)
        m = re.search('boundary=([a-zA-Z]+)', headers['Content-Type'])
        boundary = m.group(1)
        self.assertEqual({
            'Content-Type': "multipart/form-data; boundary=%s" % boundary,
            'Content-Length': str(len(data)),
            }, headers)
        self.assertIsInstance(data, bytes)
        self.assertEquals(
            '--%s\r\nContent-Disposition: form-data; name="%s"; filename="%s"'
            '\r\nContent-Type: application/octet-stream\r\n\r\n%s\r\n--%s--'
            '\r\n' % (boundary, file, file, content, boundary),
            data.decode('utf-8'))

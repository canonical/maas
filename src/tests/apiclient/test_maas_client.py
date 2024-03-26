# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test MAAS HTTP API client."""

from functools import wraps
import gzip
from io import BytesIO
import json
import os
from random import randint
from unittest.mock import ANY, MagicMock, patch
import urllib.error
import urllib.parse
from urllib.parse import parse_qs, urljoin, urlparse
import urllib.request

from apiclient.maas_client import MAASClient, MAASDispatcher, MAASOAuth
from apiclient.testing.django import APIClientTestCase
from maastesting.factory import factory
from maastesting.fixtures import TempWDFixture
from maastesting.httpd import HTTPServerFixture
from maastesting.testcase import MAASTestCase


class TestMAASOAuth(MAASTestCase):
    def test_sign_request_adds_header(self):
        headers = {}
        auth = MAASOAuth("consumer_key", "resource_token", "resource_secret")
        auth.sign_request("http://example.com/", headers)
        self.assertIn("Authorization", headers)


def no_proxy(fn):
    @patch.dict(
        os.environ,
        dict.fromkeys({"http_proxy", "https_proxy", "no_proxy"}, ""),
    )
    @wraps(fn)
    def with_no_proxy(*args, **kwargs):
        return fn(*args, **kwargs)

    return with_no_proxy


class TestMAASDispatcher(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.patch_urllib()

    def patch_urllib(self):
        def patch_build_opener(*args, **kwargs):
            self.opener = real_build_opener(*args, **kwargs)
            self.orig_open_func = self.opener.open
            if self.open_func is not None:
                self.opener.open = self.open_func
            return self.opener

        real_build_opener = urllib.request.build_opener
        build_opener_mock = self.patch(urllib.request, "build_opener")
        build_opener_mock.side_effect = patch_build_opener
        self.open_func = None

    @no_proxy
    def test_dispatch_query_makes_direct_call(self):
        contents = factory.make_string().encode("ascii")
        url = "file://%s" % self.make_file(contents=contents)
        self.assertEqual(
            contents, MAASDispatcher().dispatch_query(url, {}).read()
        )

    @no_proxy
    def test_dispatch_query_encodes_string_data(self):
        # urllib, used by MAASDispatcher, requires data encoded into bytes. We
        # encode into utf-8 in dispatch_query if necessary.
        request = self.patch(urllib.request.Request, "__init__")
        self.patch_urllib()
        self.open_func = lambda *args: MagicMock()
        url = factory.make_url()
        data = factory.make_string(300, spaces=True)
        MAASDispatcher().dispatch_query(url, {}, method="POST", data=data)
        request.assert_called_once_with(ANY, url, bytes(data, "utf-8"), ANY)

    @no_proxy
    def test_request_from_http(self):
        # We can't just call self.make_file because HTTPServerFixture will only
        # serve content from the current WD. And we don't want to create random
        # content in the original WD.
        self.useFixture(TempWDFixture())
        name = factory.make_string()
        content = factory.make_string().encode("ascii")
        factory.make_file(location=".", name=name, contents=content)
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, name)
            response = MAASDispatcher().dispatch_query(url, {})
            self.assertEqual(200, response.code)
            self.assertEqual(content, response.read())

    @no_proxy
    def test_supports_any_method(self):
        # urllib2, which MAASDispatcher uses, only supports POST and
        # GET. There is some extra code that makes sure the passed
        # method is honoured which is tested here.
        self.useFixture(TempWDFixture())
        name = factory.make_string()
        content = factory.make_string(300).encode("ascii")
        factory.make_file(location=".", name=name, contents=content)

        method = "PUT"
        # The test httpd doesn't like PUT, so we'll look for it bitching
        # about that for the purposes of this test.
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, name)
            e = self.assertRaises(
                urllib.error.HTTPError,
                MAASDispatcher().dispatch_query,
                url,
                {},
                method=method,
            )
            self.assertIn("Unsupported method ('PUT')", e.reason)

    @no_proxy
    def test_supports_content_encoding_gzip(self):
        # The client will set the Accept-Encoding: gzip header, and it will
        # also decompress the response if it comes back with Content-Encoding:
        # gzip.
        self.useFixture(TempWDFixture())
        name = factory.make_string()
        content = factory.make_string(300).encode("ascii")
        factory.make_file(location=".", name=name, contents=content)
        called = []

        def logging_open(*args, **kwargs):
            called.append((args, kwargs))
            return self.orig_open_func(*args, **kwargs)

        self.open_func = logging_open
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, name)
            res = MAASDispatcher().dispatch_query(url, {})
            self.assertEqual(200, res.code)
            self.assertEqual(content, res.read())
        request = called[0][0][0]
        self.assertEqual([((request,), {})], called)
        self.assertEqual("gzip", request.headers.get("Accept-encoding"))

    @no_proxy
    def test_doesnt_override_accept_encoding_headers(self):
        # If someone passes their own Accept-Encoding header, then dispatch
        # just passes it through.
        self.useFixture(TempWDFixture())
        name = factory.make_string()
        content = factory.make_string(300).encode("ascii")
        factory.make_file(location=".", name=name, contents=content)
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, name)
            headers = {"Accept-encoding": "gzip"}
            res = MAASDispatcher().dispatch_query(url, headers)
            self.assertEqual(200, res.code)
            self.assertEqual("gzip", res.info().get("Content-Encoding"))
            raw_content = res.read()
        read_content = gzip.GzipFile(
            mode="rb", fileobj=BytesIO(raw_content)
        ).read()
        self.assertEqual(content, read_content)

    @no_proxy
    def test_retries_three_times_on_503_service_unavailable(self):
        self.useFixture(TempWDFixture())
        name = factory.make_string()
        content = factory.make_string().encode("ascii")
        factory.make_file(location=".", name=name, contents=content)
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, name)

            counter = {"count": 0}

            def _wrap_open(*args, **kwargs):
                if counter["count"] < 2:
                    counter["count"] += 1
                    raise urllib.error.HTTPError(
                        url, 503, "service unavailable", {}, None
                    )
                else:
                    return self.orig_open_func(*args, **kwargs)

            self.open_func = _wrap_open
            response = MAASDispatcher().dispatch_query(url, {})
            self.assertEqual(200, response.code)
            self.assertEqual(content, response.read())

    @no_proxy
    def test_retries_three_times_raises_503_service_unavailable(self):
        self.useFixture(TempWDFixture())
        name = factory.make_string()
        content = factory.make_string().encode("ascii")
        factory.make_file(location=".", name=name, contents=content)
        with HTTPServerFixture() as httpd:
            url = urljoin(httpd.url, name)

            def _wrap_open(*args, **kwargs):
                raise urllib.error.HTTPError(
                    url, 503, "service unavailable", {}, None
                )

            self.open_func = _wrap_open
            err = self.assertRaises(
                urllib.error.HTTPError,
                MAASDispatcher().dispatch_query,
                url,
                {},
            )
            self.assertEqual(503, err.code)

    def test_autodetects_proxies(self):
        self.open_func = lambda *args: MagicMock()
        url = factory.make_url()
        proxy_variables = {
            "http_proxy": "http://proxy.example.com",
            "https_proxy": "https://proxy.example.com",
            "no_proxy": "noproxy.example.com",
        }
        with patch.dict(os.environ, proxy_variables):
            MAASDispatcher().dispatch_query(url, {}, method="GET")
        for handler in self.opener.handle_open["http"]:
            if isinstance(handler, urllib.request.ProxyHandler):
                break
        else:
            raise AssertionError("No ProxyHandler installed")
        expected = {
            "http": proxy_variables["http_proxy"],
            "https": proxy_variables["https_proxy"],
            "no": proxy_variables["no_proxy"],
        }
        for key, value in expected.items():
            self.assertEqual(value, handler.proxies[key])

    def test_no_autodetects_proxies(self):
        self.open_func = lambda *args: MagicMock()
        url = factory.make_url()
        proxy_variables = {
            "http_proxy": "http://proxy.example.com",
            "https_proxy": "https://proxy.example.com",
            "no_proxy": "noproxy.example.com",
        }
        with patch.dict(os.environ, proxy_variables):
            dispatcher = MAASDispatcher(autodetect_proxies=False)
            dispatcher.dispatch_query(url, {}, method="GET")
        for handler in self.opener.handle_open["http"]:
            if isinstance(handler, urllib.request.ProxyHandler):
                raise AssertionError("ProxyHandler shouldn't be there")


def make_path():
    """Create an arbitrary resource path."""
    return "/" + "/".join(factory.make_string() for counter in range(2))


class FakeDispatcher:
    """Fake MAASDispatcher.  Records last invocation, returns given result."""

    last_call = None

    def __init__(self, result=None):
        self.result = result

    def dispatch_query(
        self, request_url, headers, method=None, data=None, insecure=False
    ):
        self.last_call = {
            "request_url": request_url,
            "headers": headers,
            "method": method,
            "data": data,
            "insecure": insecure,
        }
        return self.result


def make_client(root=None, result=None):
    """Create a MAASClient."""
    if root is None:
        root = factory.make_simple_http_url(
            path=factory.make_name("path") + "/"
        )
    auth = MAASOAuth(
        factory.make_string(), factory.make_string(), factory.make_string()
    )
    return MAASClient(auth, FakeDispatcher(result=result), root)


class TestMAASClient(APIClientTestCase):
    def test_make_url_joins_root_and_path(self):
        path = make_path()
        client = make_client()
        expected = client.url.rstrip("/") + "/" + path.lstrip("/")
        self.assertEqual(expected, client._make_url(path))

    def test_make_url_removes_duplicate_MAAS(self):
        path = "/MAAS/api/2.0/machines/"
        client = make_client(root="http://example.com/MAAS/")
        self.assertEqual(
            "http://example.com/MAAS/api/2.0/machines/", client._make_url(path)
        )

    def test_make_url_converts_sequence_to_path(self):
        path = ["top", "sub", "leaf"]
        client = make_client(root="http://example.com/")
        self.assertEqual(
            "http://example.com/top/sub/leaf", client._make_url(path)
        )

    def test_make_url_represents_path_components_as_text(self):
        number = randint(0, 100)
        client = make_client()
        self.assertEqual(
            urljoin(client.url, str(number)), client._make_url([number])
        )

    def test_formulate_get_makes_url(self):
        path = make_path()
        client = make_client()
        url, headers = client._formulate_get(path)
        expected = client.url.rstrip("/") + "/" + path.lstrip("/")
        self.assertEqual(expected, url)

    def test_formulate_get_adds_parameters_to_url(self):
        params = {
            factory.make_string(): factory.make_string()
            for counter in range(3)
        }
        url, headers = make_client()._formulate_get(make_path(), params)
        expectation = {key: [value] for key, value in params.items()}
        self.assertEqual(expectation, parse_qs(urlparse(url).query))

    def test_formulate_get_adds_list_parameters_to_url(self):
        params = {
            factory.make_string(): [factory.make_string() for _ in range(2)],
            factory.make_string(): [factory.make_string() for _ in range(2)],
        }
        k = list(params.keys())
        v = [value for values in params.values() for value in values]
        url, headers = make_client()._formulate_get(make_path(), params)
        url_args = url.split("?")[1]
        self.assertEqual(
            "%s=%s&%s=%s&%s=%s&%s=%s"
            % (k[0], v[0], k[0], v[1], k[1], v[2], k[1], v[3]),
            url_args,
        )

    def test_flatten_flattens_out_list(self):
        number = randint(0, 10)
        key = factory.make_string()
        param_list = [factory.make_string() for counter in range(number)]
        params = {key: param_list}
        flattend_list = list(make_client()._flatten(params))
        expectation = [(key, value) for value in param_list]
        self.assertEqual(expectation, flattend_list)

    def test_formulate_get_signs_request(self):
        url, headers = make_client()._formulate_get(make_path())
        self.assertIn("Authorization", headers)

    def test_formulate_change_makes_url(self):
        path = make_path()
        client = make_client()
        url, headers, body = client._formulate_change(path, {})
        expected = client.url.rstrip("/") + "/" + path.lstrip("/")
        self.assertEqual(expected, url)

    def test_formulate_change_signs_request(self):
        url, headers, body = make_client()._formulate_change(make_path(), {})
        self.assertIn("Authorization", headers)

    def test_formulate_change_passes_parameters_in_body(self):
        params = {factory.make_string(): factory.make_string()}
        url, headers, body = make_client()._formulate_change(
            make_path(), params
        )
        post, _ = self.parse_headers_and_body_with_django(headers, body)
        self.assertEqual(
            {name: [value] for name, value in params.items()}, post
        )

    def test_formulate_change_as_json(self):
        params = {factory.make_string(): factory.make_string()}
        url, headers, body = make_client()._formulate_change(
            make_path(), params, as_json=True
        )
        self.assertEqual(headers.get("Content-Type"), "application/json")
        self.assertEqual(headers.get("Content-Length"), str(len(body)))
        self.assertEqual(json.loads(body), params)
        data = self.parse_headers_and_body_with_mimer(headers, body)
        self.assertEqual(params, data)

    def test_get_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        client.get(path)
        request = client.dispatcher.last_call
        self.assertEqual(client._make_url(path), request["request_url"])
        self.assertIn("Authorization", request["headers"])
        self.assertEqual("GET", request["method"])
        self.assertIsNone(request["data"])

    def test_get_without_op_gets_simple_resource(self):
        expected_result = factory.make_string()
        client = make_client(result=expected_result)
        result = client.get(make_path())
        self.assertEqual(expected_result, result)

    def test_get_with_op_queries_resource(self):
        path = make_path()
        method = factory.make_string()
        client = make_client()
        client.get(path, method)
        dispatch = client.dispatcher.last_call
        self.assertEqual(
            client._make_url(path) + "?op=%s" % method, dispatch["request_url"]
        )

    def test_get_passes_parameters(self):
        path = make_path()
        param = factory.make_string()
        method = factory.make_string()
        client = make_client()
        client.get(path, method, parameter=param)
        request = client.dispatcher.last_call
        self.assertIsNone(request["data"])
        query = parse_qs(urlparse(request["request_url"]).query)
        self.assertCountEqual([param], query["parameter"])

    def test_post_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        method = factory.make_string()
        client.post(path, method)
        request = client.dispatcher.last_call
        self.assertEqual(
            client._make_url(path) + f"?op={method}",
            request["request_url"],
        )
        self.assertIn("Authorization", request["headers"])
        self.assertEqual("POST", request["method"])

    def test_post_passes_parameters(self):
        param = factory.make_string()
        method = factory.make_string()
        client = make_client()
        client.post(make_path(), method, parameter=param)
        request = client.dispatcher.last_call
        post, _ = self.parse_headers_and_body_with_django(
            request["headers"], request["data"]
        )
        self.assertTrue(request["request_url"].endswith(f"?op={method}"))
        self.assertEqual({"parameter": [param]}, post)

    def test_post_as_json(self):
        param = factory.make_string()
        method = factory.make_string()
        list_param = [factory.make_string() for _ in range(10)]
        client = make_client()
        client.post(
            make_path(),
            method,
            as_json=True,
            param=param,
            list_param=list_param,
        )
        request = client.dispatcher.last_call
        self.assertEqual(
            "application/json", request["headers"].get("Content-Type")
        )
        content = self.parse_headers_and_body_with_mimer(
            request["headers"], request["data"]
        )
        self.assertTrue(request["request_url"].endswith(f"?op={method}"))
        self.assertEqual({"param": param, "list_param": list_param}, content)

    def test_post_without_op(self):
        path = make_path()
        param = factory.make_string()
        method = None
        client = make_client()

        client.post(path, method, parameter=param)
        request = client.dispatcher.last_call
        post, _ = self.parse_headers_and_body_with_django(
            request["headers"], request["data"]
        )
        self.assertTrue(request["request_url"].endswith(path))
        self.assertEqual({"parameter": [param]}, post)

    def test_put_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        client.put(path, parameter=factory.make_string())
        request = client.dispatcher.last_call
        self.assertEqual(client._make_url(path), request["request_url"])
        self.assertIn("Authorization", request["headers"])
        self.assertEqual("PUT", request["method"])

    def test_delete_dispatches_to_resource(self):
        path = make_path()
        client = make_client()
        client.delete(path)
        request = client.dispatcher.last_call
        self.assertEqual(client._make_url(path), request["request_url"])
        self.assertIn("Authorization", request["headers"])
        self.assertEqual("DELETE", request["method"])

    def test_delete_passes_body(self):
        # A DELETE request should have an empty body.  But we can't just leave
        # the body out altogether, or the request will hang (bug 1313556).
        client = make_client()
        client.delete(make_path())
        self.assertIsNotNone(client.dispatcher.last_call["data"])

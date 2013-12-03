# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS OAuth API connection library."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MAASClient',
    'MAASDispatcher',
    'MAASOAuth',
    ]

import gzip
from io import BytesIO
import urllib2

from apiclient.encode_json import encode_json_data
from apiclient.multipart import encode_multipart_data
from apiclient.utils import urlencode
import oauth.oauth as oauth


class MAASOAuth:
    """Helper class to OAuth-sign an HTTP request."""

    def __init__(self, consumer_key, resource_token, resource_secret):
        resource_tok_string = "oauth_token_secret=%s&oauth_token=%s" % (
            resource_secret, resource_token)
        self.resource_token = oauth.OAuthToken.from_string(resource_tok_string)
        self.consumer_token = oauth.OAuthConsumer(consumer_key, "")

    def sign_request(self, url, headers):
        """Sign a request.

        @param url: The URL to which the request is to be sent.
        @param headers: The headers in the request.  These will be updated
            with the signature.
        """
        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            self.consumer_token, token=self.resource_token, http_url=url)
        oauth_request.sign_request(
            oauth.OAuthSignatureMethod_PLAINTEXT(), self.consumer_token,
            self.resource_token)
        headers.update(oauth_request.to_header())


class NoAuth:
    """Anonymous authentication class for making unauthenticated requests."""

    def __init__(self, *args, **kwargs):
        pass

    def sign_request(self, *args, **kwargs):
        """Go through the motions of signing a request.

        Since this class does not really authenticate, this does nothing.
        """


class RequestWithMethod(urllib2.Request):
    """Enhances urllib2.Request so an http method can be supplied."""
    def __init__(self, *args, **kwargs):
        self._method = kwargs.pop('method', None)
        urllib2.Request.__init__(self, *args, **kwargs)

    def get_method(self):
        return (
            self._method if self._method
            else super(RequestWithMethod, self).get_method())


class MAASDispatcher:
    """Helper class to connect to a MAAS server using blocking requests.

    Be careful when changing its API: this class is designed so that it
    can be replaced with a Twisted-enabled alternative.  See the MAAS
    provider in Juju for the code this would require.
    """

    def dispatch_query(self, request_url, headers, method="GET", data=None):
        """Synchronously dispatch an OAuth-signed request to L{request_url}.

        :param request_url: The URL to which the request is to be sent.
        :param headers: Headers to include in the request.
        :type headers: A dict.
        :param method: The HTTP method, e.g. C{GET}, C{POST}, etc.
            An AssertionError is raised if trying to pass data for a GET.
        :param data: The data to send, if any.
        :type data: A byte string.

        :return: A open file-like object that contains the response.
        """
        headers = dict(headers)
        # header keys are case insensitive, so we have to pass over them
        set_accept_encoding = False
        for key in headers:
            if key.lower() == 'accept-encoding':
                # The user already supplied a requested encoding, so just pass
                # it along.
                break
        else:
            set_accept_encoding = True
            headers['Accept-encoding'] = 'gzip'
        req = RequestWithMethod(request_url, data, headers, method=method)
        res = urllib2.urlopen(req)
        # If we set the Accept-encoding header, then we decode the header for
        # the caller.
        is_gzip = (
            set_accept_encoding
            and res.info().get('Content-Encoding') == 'gzip')
        if is_gzip:
            # Workaround python's gzip failure, gzip.GzipFile wants to be able
            # to seek the file object.
            res_content_io = BytesIO(res.read())
            ungz = gzip.GzipFile(mode='rb', fileobj=res_content_io)
            res = urllib2.addinfourl(ungz, res.headers, res.url, res.code)
        return res


class MAASClient:
    """Base class for connecting to MAAS servers.

    All "path" parameters can be either a string describing an absolute
    resource path, or a sequence of items that, when represented as unicode,
    make up the elements of the resource's path.  So `['nodes', node_id]`
    is equivalent to `"nodes/%s" % node_id`.
    """

    def __init__(self, auth, dispatcher, base_url):
        """Intialise the client.

        :param auth: A `MAASOAuth` to sign requests.
        :param dispatcher: An object implementing the MAASOAuthConnection
            base class.
        :param base_url: The base URL for the MAAS server, e.g.
            http://my.maas.com:5240/
        """
        self.dispatcher = dispatcher
        self.auth = auth
        self.url = base_url

    def _make_url(self, path):
        """Compose an absolute URL to `path`.

        :param path: Either a string giving a path to the desired resource,
            or a sequence of items that make up the path.
        :return: An absolute URL leading to `path`.
        """
        assert not isinstance(path, bytes)
        if not isinstance(path, unicode):
            assert not any(isinstance(element, bytes) for element in path)
            path = '/'.join(unicode(element) for element in path)
        # urljoin is very sensitive to leading slashes and when spurious
        # slashes appear it removes path parts. This is why joining is
        # done manually here.
        return self.url.rstrip("/") + "/" + path.lstrip("/")

    def _formulate_get(self, path, params=None):
        """Return URL and headers for a GET request.

        This is similar to _formulate_change, except parameters are encoded
        into the URL.

        :param path: Path to the object to issue a GET on.
        :param params: Optional dict of parameter values.
        :return: A tuple: URL and headers for the request.
        """
        url = self._make_url(path)
        if params is not None and len(params) > 0:
            url += "?" + urlencode(params.items())
        headers = {}
        self.auth.sign_request(url, headers)
        return url, headers

    def _formulate_change(self, path, params, as_json=False):
        """Return URL, headers, and body for a non-GET request.

        This is similar to _formulate_get, except parameters are encoded as
        a multipart form body.

        :param path: Path to the object to issue a GET on.
        :param params: A dict of parameter values.
        :param as_json: Encode params as application/json instead of
            multipart/form-data. Only use this if you know the API already
            supports JSON requests.
        :return: A tuple: URL, headers, and body for the request.
        """
        url = self._make_url(path)
        if 'op' in params:
            params = dict(params)
            op = params.pop('op')
            url += '?' + urlencode([('op', op)])
        if as_json:
            body, headers = encode_json_data(params)
        else:
            body, headers = encode_multipart_data(params, {})
        self.auth.sign_request(url, headers)
        return url, headers, body

    def get(self, path, op=None, **kwargs):
        """Dispatch a GET.

        :param op: Optional: named GET operation to invoke.  If given, any
            keyword arguments are passed to the named operation.
        :return: The result of the dispatch_query call on the dispatcher.
        """
        if op is not None:
            kwargs['op'] = op
        url, headers = self._formulate_get(path, kwargs)
        return self.dispatcher.dispatch_query(
            url, method="GET", headers=headers)

    def post(self, path, op, as_json=False, **kwargs):
        """Dispatch POST method `op` on `path`, with the given parameters.

        :param as_json: Instead of POSTing the content as multipart/form-data
            POST it as application/json
        :return: The result of the dispatch_query call on the dispatcher.
        """
        kwargs['op'] = op
        url, headers, body = self._formulate_change(
            path, kwargs, as_json=as_json)
        return self.dispatcher.dispatch_query(
            url, method="POST", headers=headers, data=body)

    def put(self, path, **kwargs):
        """Dispatch a PUT on the resource at `path`."""
        url, headers, body = self._formulate_change(path, kwargs)
        return self.dispatcher.dispatch_query(
            url, method="PUT", headers=headers, data=body)

    def delete(self, path):
        """Dispatch a DELETE on the resource at `path`."""
        url, headers, body = self._formulate_change(path, {})
        return self.dispatcher.dispatch_query(
            url, method="DELETE", headers=headers)

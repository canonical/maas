# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS OAuth API connection library."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'MAASClient',
    'MAASDispatcher',
    'MAASOAuth',
    ]

from urllib import urlencode
import urllib2
from urlparse import urlparse

from apiclient.multipart import encode_multipart_data
import oauth.oauth as oauth


def _ascii_url(url):
    """Encode `url` as ASCII if it isn't already."""
    if isinstance(url, unicode):
        urlparts = urlparse(url)
        urlparts = urlparts._replace(
            netloc=urlparts.netloc.encode("idna"))
        url = urlparts.geturl()
    return url.encode("ascii")


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
        req = urllib2.Request(request_url, data, headers)
        return urllib2.urlopen(req)


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
        if not isinstance(path, basestring):
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
            url += "?" + urlencode(params)
        headers = {}
        self.auth.sign_request(url, headers)
        return url, headers

    def _formulate_change(self, path, params):
        """Return URL, headers, and body for a non-GET request.

        This is similar to _formulate_get, except parameters are encoded as
        a multipart form body.

        :param path: Path to the object to issue a GET on.
        :param params: A dict of parameter values.
        :return: A tuple: URL, headers, and body for the request.
        """
        url = self._make_url(path)
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

    def post(self, path, op, **kwargs):
        """Dispatch POST method `op` on `path`, with the given parameters.

        :return: The result of the dispatch_query call on the dispatcher.
        """
        kwargs['op'] = op
        url, headers, body = self._formulate_change(path, kwargs)
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

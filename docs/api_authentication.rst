.. -*- mode: rst -*-

.. _api_authentication:

API authentication
==================

MAAS's API uses OAuth_ as its authentication mechanism.  There isn't a third
party involved (as in 3-legged OAuth) and so the process used is what's
commonly referred to as 0-legged OAuth: the consumer accesses protected
resources by submitting OAuth signed requests.

.. _OAuth: http://en.wikipedia.org/wiki/OAuth

Note that some API endpoints support unauthenticated requests (i.e.
anonymous access).  See the :doc:`API documentation <api>` for details.


Examples
========

Here are two examples on how to perform an authenticated GET request to
retrieve the list of nodes.  The <key>, <secret>, <consumer_key> tokens
are the three elements that compose the API key (API key =
'<consumer_key>:<key>:<secret>').

Python
------

.. code:: python

    import oauth.oauth as oauth
    import httplib2
    import uuid

    def perform_API_request(site, uri, method, key, secret, consumer_key):
        resource_tok_string = "oauth_token_secret=%s&oauth_token=%s" % (
            secret, key)
        resource_token = oauth.OAuthToken.from_string(resource_tok_string)
        consumer_token = oauth.OAuthConsumer(consumer_key, "")

        oauth_request = oauth.OAuthRequest.from_consumer_and_token(
            consumer_token, token=resource_token, http_url=site,
            parameters={'oauth_nonce': uuid.uuid4().hex})
        oauth_request.sign_request(
            oauth.OAuthSignatureMethod_PLAINTEXT(), consumer_token,
            resource_token)
        headers = oauth_request.to_header()
        url = "%s%s" % (site, uri)
        http = httplib2.Http()
        return http.request(url, method, body=None, headers=headers)

    # API key = '<consumer_key>:<key>:<secret>'
    response = perform_API_request(
        'http://server/MAAS/api/1.0', '/nodes/?op=list', 'GET', '<key>', '<secret>',
        '<consumer_key>')

Ruby
----

.. code:: ruby

    require 'oauth'
    require 'oauth/signature/plaintext'

    def perform_API_request(site, uri, key, secret, consumer_key)
        consumer = OAuth::Consumer.new(
            consumer_key, "",
            { :site => "http://localhost/MAAS/api/1.0",
              :scheme => :header, :signature_method => "PLAINTEXT"})
        access_token = OAuth::AccessToken.new(consumer, key, secret)
        return access_token.request(:get, "/nodes/?op=list")
    end

    # API key = "<consumer_key>:<key>:<secret>"
    response = perform_API_request(
         "http://server/MAAS/api/1.0", "/nodes/?op=list", "<key>", "<secret>",
         "consumer_key>")

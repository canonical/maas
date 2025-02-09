# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS CLI authentication."""

from getpass import getpass
import http.client
import sys
from urllib.parse import urljoin

from macaroonbakery import httpbakery

from apiclient.creds import convert_string_to_tuple
from maascli.api import Action, http_request


class UnexpectedResponse(Exception):
    """Unexpected API response."""


def try_getpass(prompt):
    """Call `getpass`, ignoring EOF errors."""
    try:
        return getpass(prompt)
    except EOFError:
        return None


def get_apikey_via_macaroon(url, ca_certs=None, insecure=False):
    """Try to get an API key using a macaroon.

    httpbakery is used to create a new API token. If the MAAS server supports
    macaroons, it will reply that a macaroon discharge is required, and bakery
    will send the user to Candid for authentication, and then call the API
    again with the acquired macaroon.

    If the MAAS server doesn't support macaroons, None is returned.

    """
    verify = True
    if insecure:
        verify = False
    elif ca_certs:
        verify = str(ca_certs)
    url = url.strip("/")
    client = httpbakery.Client()
    resp = client.request(
        "POST", f"{url}/account/?op=create_authorisation_token", verify=verify
    )
    if resp.status_code != 200:
        # Most likely the MAAS server doesn't support macaroons.
        return None
    result = resp.json()
    return "{consumer_key}:{token_key}:{token_secret}".format(**result)


def obtain_credentials(url, credentials, ca_certs=None, insecure=False):
    """Prompt for credentials if possible.

    If the credentials are "-" then read from stdin without interactive
    prompting.
    """
    if credentials == "-":
        credentials = sys.stdin.readline().strip()
    elif credentials is None:
        credentials = get_apikey_via_macaroon(
            url, ca_certs=ca_certs, insecure=insecure
        )
        if credentials is None:
            credentials = try_getpass(
                "API key (leave empty for anonymous access): "
            )
    # Ensure that the credentials have a valid form.
    if credentials and not credentials.isspace():
        return convert_string_to_tuple(credentials)
    else:
        return None


def check_valid_apikey(url, credentials, ca_certs=None, insecure=False):
    """Check for valid apikey.

    :param credentials: A 3-tuple of credentials.
    """
    if "/api/1.0" in url:
        check_url = urljoin(url, "nodegroups/")
        uri, body, headers = Action.prepare_payload(
            op="list", method="GET", uri=check_url, data=[]
        )
    else:
        check_url = urljoin(url, "users/")
        uri, body, headers = Action.prepare_payload(
            op="whoami", method="GET", uri=check_url, data=[]
        )

    # Headers are returned as a list, but they must be a dict for
    # the signing machinery.
    headers = dict(headers)

    Action.sign(uri, headers, credentials)

    response, content = http_request(
        uri,
        method="GET",
        body=body,
        headers=headers,
        ca_certs=ca_certs,
        insecure=insecure,
    )

    status = int(response["status"])
    if status == http.client.UNAUTHORIZED:
        return False
    elif status == http.client.OK:
        return True
    else:
        raise UnexpectedResponse(
            "The MAAS server gave an unexpected response: %s" % status
        )

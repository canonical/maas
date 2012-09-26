# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interact with a remote MAAS server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "register",
    ]

from getpass import getpass
import httplib
import json
import sys
from urllib import urlencode
from urlparse import (
    urljoin,
    urlparse,
    )

from apiclient.creds import (
    convert_string_to_tuple,
    convert_tuple_to_string,
    )
from apiclient.maas_client import MAASOAuth
from apiclient.multipart import encode_multipart_data
from apiclient.utils import ascii_url
import httplib2
from maascli import (
    Command,
    CommandError,
    )
from maascli.config import ProfileConfig
from maascli.utils import (
    ensure_trailing_slash,
    handler_command_name,
    parse_docstring,
    safe_name,
    )


def try_getpass(prompt):
    """Call `getpass`, ignoring EOF errors."""
    try:
        return getpass(prompt)
    except EOFError:
        return None


def obtain_credentials(credentials):
    """Prompt for credentials if possible.

    If the credentials are "-" then read from stdin without interactive
    prompting.
    """
    if credentials == "-":
        credentials = sys.stdin.readline().strip()
    elif credentials is None:
        credentials = try_getpass(
            "API key (leave empty for anonymous access): ")
    # Ensure that the credentials have a valid form.
    if credentials and not credentials.isspace():
        return convert_string_to_tuple(credentials)
    else:
        return None


def fetch_api_description(url):
    """Obtain the description of remote API given its base URL."""
    url_describe = urljoin(url, "describe/")
    http = httplib2.Http()
    response, content = http.request(
        ascii_url(url_describe), "GET")
    if response.status != httplib.OK:
        raise CommandError(
            "{0.status} {0.reason}:\n{1}".format(response, content))
    if response["content-type"] != "application/json":
        raise CommandError(
            "Expected application/json, got: %(content-type)s" % response)
    return json.loads(content)


class cmd_login(Command):
    """Log-in to a remote API, storing its description and credentials.

    If credentials are not provided on the command-line, they will be prompted
    for interactively.
    """

    def __init__(self, parser):
        super(cmd_login, self).__init__(parser)
        parser.add_argument(
            "profile_name", metavar="profile-name", help=(
                "The name with which you will later refer to this remote "
                "server and credentials within this tool."
                ))
        parser.add_argument(
            "url", help=(
                "The URL of the remote API, e.g. "
                "http://example.com/MAAS/api/1.0/"))
        parser.add_argument(
            "credentials", nargs="?", default=None, help=(
                "The credentials, also known as the API key, for the "
                "remote MAAS server. These can be found in the user "
                "preferences page in the web UI; they take the form of "
                "a long random-looking string composed of three parts, "
                "separated by colons."
                ))
        parser.set_defaults(credentials=None)

    def __call__(self, options):
        # Try and obtain credentials interactively if they're not given, or
        # read them from stdin if they're specified as "-".
        credentials = obtain_credentials(options.credentials)
        # Normalise the remote service's URL.
        url = ensure_trailing_slash(options.url)
        # Get description of remote API.
        description = fetch_api_description(url)
        # Save the config.
        profile_name = options.profile_name
        with ProfileConfig.open() as config:
            config[profile_name] = {
                "credentials": credentials,
                "description": description,
                "name": profile_name,
                "url": url,
                }


class cmd_refresh(Command):
    """Refresh the API descriptions of all profiles."""

    def __call__(self, options):
        with ProfileConfig.open() as config:
            for profile_name in config:
                profile = config[profile_name]
                url = profile["url"]
                profile["description"] = fetch_api_description(url)
                config[profile_name] = profile


class cmd_logout(Command):
    """Log-out of a remote API, purging any stored credentials."""

    def __init__(self, parser):
        super(cmd_logout, self).__init__(parser)
        parser.add_argument(
            "profile_name", metavar="profile-name", help=(
                "The name with which a remote server and its credentials "
                "are referred to within this tool."
                ))

    def __call__(self, options):
        with ProfileConfig.open() as config:
            del config[options.profile_name]


class cmd_list(Command):
    """List remote APIs that have been logged-in to."""

    def __call__(self, options):
        with ProfileConfig.open() as config:
            for profile_name in config:
                profile = config[profile_name]
                url = profile["url"]
                creds = profile["credentials"]
                if creds is None:
                    print(profile_name, url)
                else:
                    creds = convert_tuple_to_string(creds)
                    print(profile_name, url, creds)


class Action(Command):
    """A generic MAAS API action.

    This is used as a base for creating more specific commands; see
    `register_actions`.

    **Note** that this class conflates two things: CLI exposure and API
    client. The client in apiclient.maas_client is not quite suitable yet, but
    it should be iterated upon to make it suitable.
    """

    # Override these in subclasses; see `register_actions`.
    profile = handler = action = None

    uri = property(lambda self: self.handler["uri"])
    method = property(lambda self: self.action["method"])
    is_restful = property(lambda self: self.action["restful"])
    credentials = property(lambda self: self.profile["credentials"])
    op = property(lambda self: self.action["op"])

    def __init__(self, parser):
        super(Action, self).__init__(parser)
        for param in self.handler["params"]:
            parser.add_argument(param)
        parser.add_argument(
            "data", type=self.name_value_pair, nargs="*")

    def __call__(self, options):
        # TODO: this is el-cheapo URI Template
        # <http://tools.ietf.org/html/rfc6570> support; use uritemplate-py
        # <https://github.com/uri-templates/uritemplate-py> here?
        uri = self.uri.format(**vars(options))

        # Add the operation to the data set.
        if self.op is not None:
            options.data.append(("op", self.op))

        # Bundle things up ready to throw over the wire.
        uri, body, headers = self.prepare_payload(
            self.method, self.is_restful, uri, options.data)

        # Sign request if credentials have been provided.
        if self.credentials is not None:
            self.sign(uri, headers, self.credentials)

        # Use httplib2 instead of urllib2 (or MAASDispatcher, which is based
        # on urllib2) so that we get full control over HTTP method. TODO:
        # create custom MAASDispatcher to use httplib2 so that MAASClient can
        # be used.
        http = httplib2.Http()
        response, content = http.request(
            uri, self.method, body=body, headers=headers)

        # TODO: decide on how to display responses to users.
        self.print_response(response, content)

        # 2xx status codes are all okay.
        if response.status // 100 != 2:
            raise CommandError(2)

    @staticmethod
    def name_value_pair(string):
        parts = string.split("=", 1)
        if len(parts) == 2:
            return parts
        else:
            raise CommandError(
                "%r is not a name=value pair" % string)

    @staticmethod
    def prepare_payload(method, is_restful, uri, data):
        """Return the URI (modified perhaps) and body and headers.

        :param method: The HTTP method.
        :param is_restful: Is this a ReSTful operation?
        :param uri: The URI of the action.
        :param data: A dict or iterable of name=value pairs to pack into the
            body or headers, depending on the type of request.
        """
        if method == "POST" and not is_restful:
            # Encode the data as multipart for non-ReSTful POST requests; all
            # others should use query parameters. TODO: encode_multipart_data
            # insists on a dict for the data, which prevents specifying
            # multiple values for a field, like mac_addresses.  This needs to
            # be fixed.
            body, headers = encode_multipart_data(data, {})
            # TODO: make encode_multipart_data work with arbitrarily encoded
            # strings; atm, it blows up when encountering a non-ASCII string.
        else:
            # TODO: deal with state information, i.e. where to stuff CRUD
            # data, content types, etc.
            body, headers = None, {}
            # TODO: smarter merging of data with query.
            uri = urlparse(uri)._replace(query=urlencode(data)).geturl()

        return uri, body, headers

    @staticmethod
    def sign(uri, headers, credentials):
        """Sign the URI and headers."""
        auth = MAASOAuth(*credentials)
        auth.sign_request(uri, headers)

    @classmethod
    def print_response(cls, response, content):
        """Show an HTTP response in a human-friendly way."""
        # Print the response.
        print(response.status, response.reason)
        print()
        cls.print_headers(response)
        print()
        print(content)

    @staticmethod
    def print_headers(headers):
        """Show an HTTP response in a human-friendly way."""
        # Function to change headers like "transfer-encoding" into
        # "Transfer-Encoding".
        cap = lambda header: "-".join(
            part.capitalize() for part in header.split("-"))
        # Format string to prettify reporting of response headers.
        form = "%%%ds: %%s" % (
            max(len(header) for header in headers) + 2)
        # Print the response.
        for header in sorted(headers):
            print(form % (cap(header), headers[header]))


def register_actions(profile, handler, parser):
    """Register a handler's actions."""
    for action in handler["actions"]:
        help_title, help_body = parse_docstring(action["doc"])
        action_name = safe_name(action["name"]).encode("ascii")
        action_bases = (Action,)
        action_ns = {
            "action": action,
            "handler": handler,
            "profile": profile,
            }
        action_class = type(action_name, action_bases, action_ns)
        action_parser = parser.subparsers.add_parser(
            action_name, help=help_title, description=help_body)
        action_parser.set_defaults(
            execute=action_class(action_parser))


def register_handlers(profile, parser):
    """Register a profile's handlers."""
    description = profile["description"]
    for handler in description["handlers"]:
        help_title, help_body = parse_docstring(handler["doc"])
        handler_name = handler_command_name(handler["name"])
        handler_parser = parser.subparsers.add_parser(
            handler_name, help=help_title, description=help_body)
        register_actions(profile, handler, handler_parser)


def register(module, parser):
    """Register profiles."""
    with ProfileConfig.open() as config:
        for profile_name in config:
            profile = config[profile_name]
            profile_parser = parser.subparsers.add_parser(
                profile["name"], help="Interact with %(url)s" % profile)
            register_handlers(profile, profile_parser)

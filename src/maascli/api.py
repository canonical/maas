# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interact with a remote MAAS server."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "register_api_commands",
    ]

from collections import defaultdict
from email.message import Message
import httplib
from itertools import chain
import json
from operator import itemgetter
import sys
from textwrap import (
    dedent,
    fill,
    )
from urlparse import (
    urljoin,
    urlparse,
    )

from apiclient.maas_client import MAASOAuth
from apiclient.multipart import encode_multipart_data
from apiclient.utils import (
    ascii_url,
    urlencode,
    )
import httplib2
from maascli.command import (
    Command,
    CommandError,
    )
from maascli.config import ProfileConfig
from maascli.utils import (
    handler_command_name,
    parse_docstring,
    safe_name,
    )


def http_request(url, method, body=None, headers=None,
                 insecure=False):
    """Issue an http request."""
    http = httplib2.Http(
        disable_ssl_certificate_validation=insecure)
    try:
        return http.request(url, method, body=body, headers=headers)
    except httplib2.SSLHandshakeError:
        raise CommandError(
            "Certificate verification failed, use --insecure/-k to "
            "disable the certificate check.")


def fetch_api_description(url, insecure=False):
    """Obtain the description of remote API given its base URL."""
    url_describe = urljoin(url, "describe/")
    response, content = http_request(
        ascii_url(url_describe), "GET", insecure=insecure)
    if response.status != httplib.OK:
        raise CommandError(
            "{0.status} {0.reason}:\n{1}".format(response, content))
    if response["content-type"] != "application/json":
        raise CommandError(
            "Expected application/json, got: %(content-type)s" % response)
    return json.loads(content)


def get_response_content_type(response):
    """Returns the response's content-type, without parameters.

    If the content-type was not set in the response, returns `None`.

    :type response: :class:`httplib2.Response`
    """
    try:
        content_type = response["content-type"]
    except KeyError:
        return None
    else:
        # It seems odd to create a Message instance here, but at the time of
        # writing it's the only place that has the smarts to correctly deal
        # with a Content-Type that contains a charset (or other parameters).
        message = Message()
        message.set_type(content_type)
        return message.get_content_type()


def is_response_textual(response):
    """Is the response body text?"""
    content_type = get_response_content_type(response)
    return (
        content_type.endswith("/json") or
        content_type.startswith("text/"))


def print_headers(headers, file=sys.stdout):
    """Show an HTTP response in a human-friendly way.

    :type headers: :class:`httplib2.Response`, or :class:`dict`
    """
    # Function to change headers like "transfer-encoding" into
    # "Transfer-Encoding".
    cap = lambda header: "-".join(
        part.capitalize() for part in header.split("-"))
    # Format string to prettify reporting of response headers.
    form = "%%%ds: %%s" % (
        max(len(header) for header in headers) + 2)
    # Print the response.
    for header in sorted(headers):
        print(form % (cap(header), headers[header]), file=file)


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
    credentials = property(lambda self: self.profile["credentials"])
    op = property(lambda self: self.action["op"])

    def __init__(self, parser):
        super(Action, self).__init__(parser)
        for param in self.handler["params"]:
            parser.add_argument(param)
        parser.add_argument(
            "data", type=self.name_value_pair, nargs="*")
        parser.add_argument(
            "-d", "--debug", action="store_true", default=False,
            help="Display more information about API responses.")
        parser.add_argument(
            '-k', '--insecure', action='store_true', help=(
                "Disable SSL certificate check"), default=False)

    def __call__(self, options):
        # TODO: this is el-cheapo URI Template
        # <http://tools.ietf.org/html/rfc6570> support; use uritemplate-py
        # <https://github.com/uri-templates/uritemplate-py> here?
        uri = self.uri.format(**vars(options))

        # Bundle things up ready to throw over the wire.
        uri, body, headers = self.prepare_payload(
            self.op, self.method, uri, options.data)

        # Sign request if credentials have been provided.
        if self.credentials is not None:
            self.sign(uri, headers, self.credentials)

        # Use httplib2 instead of urllib2 (or MAASDispatcher, which is based
        # on urllib2) so that we get full control over HTTP method. TODO:
        # create custom MAASDispatcher to use httplib2 so that MAASClient can
        # be used.
        insecure = options.insecure
        response, content = http_request(
            uri, self.method, body=body, headers=headers,
            insecure=insecure)

        # Output.
        if options.debug:
            self.print_debug(response)
        self.print_response(response, content)

        # 2xx status codes are all okay.
        if response.status // 100 != 2:
            raise CommandError(2)

    @staticmethod
    def name_value_pair(string):
        parts = string.split("=", 1)
        if len(parts) == 2:
            return tuple(parts)
        else:
            raise CommandError(
                "%r is not a name=value pair" % string)

    @staticmethod
    def prepare_payload(op, method, uri, data):
        """Return the URI (modified perhaps) and body and headers.

        - For GET requests, encode parameters in the query string.

        - Otherwise always encode parameters in the request body.

        - Except op; this can always go in the query string.

        :param method: The HTTP method.
        :param uri: The URI of the action.
        :param data: A dict or iterable of name=value pairs to pack into the
            body or headers, depending on the type of request.
        """
        if method == "GET":
            query = data if op is None else chain([("op", op)], data)
            body, headers = None, {}
        else:
            query = [] if op is None else [("op", op)]
            if data:
                body, headers = encode_multipart_data(data)
            else:
                body, headers = None, {}

        uri = urlparse(uri)._replace(query=urlencode(query)).geturl()
        return uri, body, headers

    @staticmethod
    def sign(uri, headers, credentials):
        """Sign the URI and headers."""
        auth = MAASOAuth(*credentials)
        auth.sign_request(uri, headers)

    @staticmethod
    def print_debug(response):
        """Dump the response line and headers to stderr."""
        print(response.status, response.reason, file=sys.stderr)
        print(file=sys.stderr)
        print_headers(response, file=sys.stderr)
        print(file=sys.stderr)

    @classmethod
    def print_response(cls, response, content, file=sys.stdout):
        """Write the response's content to stdout.

        If the response is textual, a trailing \n is appended.
        """
        file.write(content)
        if is_response_textual(response) and file.isatty():
            file.write("\n")


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
            action_name, help=help_title, description=help_title,
            epilog=help_body)
        action_parser.set_defaults(
            execute=action_class(action_parser))


def register_handler(profile, handler, parser):
    """Register a resource's handler."""
    help_title, help_body = parse_docstring(handler["doc"])
    handler_name = handler_command_name(handler["name"])
    handler_parser = parser.subparsers.add_parser(
        handler_name, help=help_title, description=help_title,
        epilog=help_body)
    register_actions(profile, handler, handler_parser)


def register_resources(profile, parser):
    """Register a profile's resources."""
    anonymous = profile["credentials"] is None
    description = profile["description"]
    resources = description["resources"]
    for resource in sorted(resources, key=itemgetter("name")):
        # Don't consider the authenticated handler if this profile has no
        # credentials associated with it.
        if anonymous:
            handlers = [resource["anon"]]
        else:
            handlers = [resource["auth"], resource["anon"]]
        # Merge actions from the active handlers. This could be slightly
        # simpler using a dict and going through the handlers in reverse, but
        # doing it forwards with a defaultdict(list) leaves an easier-to-debug
        # structure, and ought to be easier to understand.
        actions = defaultdict(list)
        for handler in handlers:
            if handler is not None:
                for action in handler["actions"]:
                    action_name = action["name"]
                    actions[action_name].append(action)
        # Always represent this resource using the authenticated handler, if
        # defined, before the fall-back anonymous handler, even if this
        # profile does not have credentials.
        represent_as = dict(
            resource["auth"] or resource["anon"],
            name=resource["name"], actions=[])
        # Each value in the actions dict is a list of one or more action
        # descriptions. Here we register the handler with only the first of
        # each of those.
        if len(actions) != 0:
            represent_as["actions"].extend(
                value[0] for value in actions.values())
            register_handler(profile, represent_as, parser)

profile_help_paragraphs = [
    """\
    This is a profile.  Any commands you issue on this
    profile will operate on the MAAS region server.
    """,
    """\
    The command information you see here comes from the
    region server's API; it may differ for different
    profiles.  If you believe the API may have changed,
    use the command's 'refresh' sub-command to fetch the
    latest version of this help information from the
    server.
    """,
]
profile_help = '\n\n'.join(
    fill(dedent(paragraph)) for paragraph in profile_help_paragraphs)


def register_api_commands(parser):
    """Register all profiles as subcommands on `parser`."""
    with ProfileConfig.open() as config:
        for profile_name in config:
            profile = config[profile_name]
            profile_parser = parser.subparsers.add_parser(
                profile["name"], help="Interact with %(url)s" % profile,
                description=(
                    "Issue commands to the MAAS region controller at %(url)s."
                    % profile),
                epilog=profile_help)
            register_resources(profile, profile_parser)

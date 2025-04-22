# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interact with a remote MAAS server."""


import argparse
from contextlib import suppress
from functools import partial
import http.client
import json
from operator import itemgetter
from pathlib import Path
import re
import sys
from textwrap import dedent, fill, wrap
from urllib.parse import urljoin, urlparse

import httplib2

from apiclient.maas_client import MAASOAuth
from apiclient.multipart import (
    build_multipart_message,
    encode_multipart_message,
)
from apiclient.utils import ascii_url, urlencode
from maascli import utils
from maascli.command import Command, CommandError
from maascli.config import ProfileConfig
from maascli.utils import (
    handler_command_name,
    parse_docstring,
    safe_name,
    try_import_module,
)


def http_request(
    url, method, body=None, headers=None, ca_certs=None, insecure=False
):
    """Issue an http request."""
    http = httplib2.Http(
        ca_certs=ca_certs, disable_ssl_certificate_validation=insecure
    )
    try:
        # XXX mpontillo 2015-12-15: Should force input to be in bytes here.
        # This calls into httplib2, which is going to call a parser which
        # expects this to be a `str`.
        if isinstance(url, bytes):
            url = url.decode("ascii")
        return http.request(url, method, body=body, headers=headers)
    except httplib2.ssl.SSLError as error:
        raise CommandError(
            "Certificate verification failed, use --insecure/-k to "
            "disable the certificate check.\n" + str(error)
        )


def fetch_api_description(url, ca_certs=None, insecure=False):
    """Obtain the description of remote API given its base URL."""
    url_describe = urljoin(url, "describe/")
    response, content = http_request(
        ascii_url(url_describe), "GET", ca_certs=ca_certs, insecure=insecure
    )
    if response.status != http.client.OK:
        raise CommandError(
            "{0.status} {0.reason}:\n{1}".format(response, content)
        )
    if response["content-type"] != "application/json":
        raise CommandError(
            "Expected application/json, got: %(content-type)s" % response
        )
    # XXX mpontillo 2015-12-15: We don't actually know that this is UTF-8, but
    # I'm keeping it here, because if it happens to be non-ASCII, chances are
    # good that it'll be UTF-8.
    return json.loads(content.decode("utf-8"))


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

    _maas_url = property(lambda self: urlparse(self.profile["url"]))
    uri = property(
        lambda self: f"{self._maas_url.scheme}://{self._maas_url.netloc}{self.handler['path']}"
    )
    method = property(lambda self: self.action["method"])
    credentials = property(lambda self: self.profile["credentials"])
    op = property(lambda self: self.action["op"])

    def __init__(self, parser):
        super().__init__(parser)
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            default=False,
            help="Display more information about API responses.",
        )
        parser.add_argument(
            "-k",
            "--insecure",
            action="store_true",
            help="Disable SSL certificate check",
            default=False,
        )

    def __call__(self, options):
        # TODO: this is el-cheapo URI Template
        # <http://tools.ietf.org/html/rfc6570> support; use uritemplate-py
        # <https://github.com/uri-templates/uritemplate-py> here?
        uri = self.uri.format(**vars(options))

        # Bundle things up ready to throw over the wire.
        data = None
        if hasattr(options, "data"):
            data = options.data
        uri, body, headers = self.prepare_payload(
            self.op, self.method, uri, data
        )

        # Headers are returned as a list, but they must be a dict for
        # the signing machinery.
        headers = dict(headers)

        # Sign request if credentials have been provided.
        if self.credentials is not None:
            self.sign(uri, headers, self.credentials)

        # Use httplib2 instead of urllib2 (or MAASDispatcher, which is based
        # on urllib2) so that we get full control over HTTP method. TODO:
        # create custom MAASDispatcher to use httplib2 so that MAASClient can
        # be used.
        insecure = options.insecure
        cacerts = materialize_certificate(self.profile)
        response, content = http_request(
            uri,
            self.method,
            body=body,
            headers=headers,
            ca_certs=cacerts,
            insecure=insecure,
        )

        # Compare API hashes to see if our version of the API is old.
        self.compare_api_hashes(self.profile, response)

        # Output.
        if options.debug:
            utils.dump_certificate_info(uri)
            utils.dump_response_summary(response)
        utils.print_response_content(response, content)

        # 2xx status codes are all okay.
        if response.status // 100 != 2:
            raise CommandError(2)

    @staticmethod
    def compare_api_hashes(profile, response):
        """Compare the local and remote API hashes.

        If they differ -- or the remote side reports a hash and there is no
        hash stored locally -- then show a warning to the user.
        """
        hash_from_response = response.get("X-MAAS-API-Hash".lower())
        if hash_from_response is not None:
            hash_from_profile = profile["description"].get("hash")
            if hash_from_profile != hash_from_response:
                warning = dedent(
                    """\
                WARNING! The API on the server differs from the description
                that is cached locally. This may result in failed API calls.
                Refresh the local API description with `maas refresh`.
                """
                )
                warning_lines = wrap(
                    warning,
                    width=70,
                    initial_indent="*** ",
                    subsequent_indent="*** ",
                )
                print("**********" * 7, file=sys.stderr)
                for warning_line in warning_lines:
                    print(warning_line, file=sys.stderr)
                print("**********" * 7, file=sys.stderr)

    @staticmethod
    def name_value_pair(string):
        """Ensure that `string` is a valid ``name:value`` pair.

        When `string` is of the form ``name=value``, this returns a
        2-tuple of ``name, value``.

        However, when `string` is of the form ``name@=value``, this
        returns a ``name, opener`` tuple, where ``opener`` is a function
        that will return an open file handle when called. The file will
        be opened in binary mode for reading only.
        """
        parts = re.split(r"(=|@=)", string, 1)
        if len(parts) == 3:
            name, what, value = parts
            if what == "=":
                return name, value
            elif what == "@=":
                return name, partial(open, value, "rb")
            else:
                raise AssertionError("Unrecognised separator %r" % what)
        else:
            raise CommandError(
                "%r is not a name=value or name@=filename pair" % string
            )

    @classmethod
    def prepare_payload(cls, op, method, uri, data):
        """Return the URI (modified perhaps) and body and headers.

        - For GET requests, encode parameters in the query string.

        - Otherwise always encode parameters in the request body.

        - Except op; this can always go in the query string.

        :param method: The HTTP method.
        :param uri: The URI of the action.
        :param data: An iterable of ``name, value`` or ``name, opener``
            tuples (see `name_value_pair`) to pack into the body or
            query, depending on the type of request.
        """
        query = [("op", op)] if op else []

        headers, body = [], None

        def slurp(opener):
            with opener() as fd:
                return fd.read()

        if method in ("GET", "DELETE") and data is not None:
            query.extend(
                (name, slurp(value) if callable(value) else value)
                for name, value in data
            )
            body, headers = None, []
        else:
            if data is None or len(data) == 0:
                body, headers = None, []
            else:
                message = build_multipart_message(data)
                headers, body = encode_multipart_message(message)

        uri = urlparse(uri)._replace(query=urlencode(query)).geturl()
        return uri, body, headers

    @staticmethod
    def sign(uri, headers, credentials):
        """Sign the URI and headers."""
        auth = MAASOAuth(*credentials)
        auth.sign_request(uri, headers)


class ActionHelp(argparse.Action):
    """Custom "help" function for an action `ArgumentParser`.

    We use the argument parser's "epilog" field for the action's detailed
    description.

    This class is stateless.
    """

    keyword_args_help = dedent(
        """\
        This method accepts keyword arguments.  Pass each argument as a
        key-value pair with an equals sign between the key and the value:
        key1=value1 key2=value key3=value3.  Keyword arguments must come after
        any positional arguments.
        """
    )

    @classmethod
    def get_positional_args(cls, parser):
        """Return an API action's positional arguments.

        Most typically, this holds a URL path fragment for the object that's
        being addressed, e.g. a physical zone's name.

        There will also be a "data" argument, representing the request's
        embedded data, but that's of no interest to end-users.  The CLI offers
        a more fine-grained interface to pass parameters, so as a special case,
        that one item is left out.
        """
        # Use private method on the parser.  The list of actions does not
        # seem to be publicly exposed.
        positional_actions = parser._get_positional_actions()
        names = [action.dest for action in positional_actions]
        if len(names) > 0 and names[-1] == "data":
            names = names[:-1]
        return names

    @classmethod
    def get_optional_args(cls, parser):
        """Return an API action's optional arguments."""
        # Use private method on the parser.  The list of actions does not
        # seem to be publicly exposed.
        optional_args = parser._get_optional_actions()
        return optional_args

    @classmethod
    def compose_positional_args(cls, parser):
        """Describe positional arguments for `parser`, as a list of strings."""
        positional_args = cls.get_positional_args(parser)
        if len(positional_args) == 0:
            return []
        else:
            return ["", "", "Positional arguments:"] + [
                "\t%s" % arg for arg in positional_args
            ]

    @classmethod
    def compose_epilog(cls, parser):
        """Describe action in detail, as a list of strings."""
        epilog = parser.epilog
        if parser.epilog is None:
            return []
        epilog = epilog.rstrip()
        if epilog == "":
            return []

        lines = ["", ""]
        if ":param " in epilog:
            # This API action documents keyword arguments.  Explain to the
            # user how those work first.
            lines.append(cls.keyword_args_help)
        # Finally, include the actual documentation body.
        lines.append(epilog)
        return lines

    @classmethod
    def compose_optional_args(cls, parser):
        """Describe optional arguments for `parser`, as a list of strings."""
        optional_args = cls.get_optional_args(parser)
        if len(optional_args) == 0:
            return []

        lines = ["", "", "Common command-line options:"]
        for arg in optional_args:
            # Minimal representation of options.  Doesn't show
            # arguments to the options, defaults, and so on.  But it's
            # all we need for now.
            lines.append("    %s" % ", ".join(arg.option_strings))
            lines.append("\t%s" % arg.help)
        return lines

    @classmethod
    def compose(cls, parser):
        """Put together, and return, help output for `parser`."""
        lines = [parser.format_usage().rstrip(), "", parser.description]
        lines += cls.compose_positional_args(parser)
        lines += cls.compose_epilog(parser)
        lines += cls.compose_optional_args(parser)
        return "\n".join(lines)

    def __call__(self, parser, namespace, values, option_string):
        """Overridable as defined by the `argparse` API."""
        print(self.compose(parser))
        sys.exit(0)


def get_action_class(handler, action):
    """Return custom action handler class."""
    handler_name = handler["handler_name"].replace("-", "_")
    action_name = "{}_{}".format(
        handler_name,
        safe_name(action["name"]).replace("-", "_"),
    )
    action_module = try_import_module("maascli.actions.%s" % action_name)
    if action_module is not None:
        return action_module.action_class
    return None


def get_action_class_bases(handler, action):
    """Return the base classes for the dynamic class."""
    action_class = get_action_class(handler, action)
    if action_class is not None:
        return (action_class,)
    return (Action,)


def register_actions(profile, handler, parser):
    """Register a handler's actions."""
    for action in handler["actions"]:
        help_title, help_body = parse_docstring(action["doc"])
        action_name = safe_name(action["name"])
        action_bases = get_action_class_bases(handler, action)
        action_ns = {"action": action, "handler": handler, "profile": profile}
        action_class = type(action_name, action_bases, action_ns)
        action_parser = parser.subparsers.add_parser(
            action_name,
            help=help_title,
            description=help_title,
            epilog=help_body,
            add_help=False,
        )
        action_parser.add_argument(
            "--help",
            "-h",
            action=ActionHelp,
            nargs=0,
            help="Show this help message and exit.",
        )
        for param in handler["params"]:
            action_parser.add_argument(param)
        # check if the action requires any extra parameters in the form of key=value pairs
        if ":param" in help_body:
            action_parser.add_argument(
                "data", type=action_class.name_value_pair, nargs="*"
            )
        action_parser.set_defaults(execute=action_class(action_parser))


def register_handler(profile, handler, parser):
    """Register a resource's handler."""
    help_title, help_body = parse_docstring(handler["doc"])
    handler_parser = parser.subparsers.add_parser(
        handler["handler_name"],
        help=help_title,
        description=help_title,
        epilog=help_body,
    )
    register_actions(profile, handler, handler_parser)


def register_resources(profile, parser):
    """Register a profile's resources."""
    anonymous = profile["credentials"] is None
    description = profile["description"]
    resources = description["resources"]

    handler_defs = []
    for resource in resources:
        # Don't consider the authenticated handler if this profile has no
        # credentials associated with it.
        if anonymous:
            handlers = [resource["anon"]]
        else:
            handlers = [resource["auth"], resource["anon"]]
        actions = {}
        for handler in handlers:
            if handler is not None:
                for action in handler["actions"]:
                    action_name = action["name"]
                    if action_name not in actions:
                        # register handler only for the first action of each
                        # name found
                        actions[action_name] = action

        if not actions:
            continue
        # Always represent this resource using the authenticated handler, if
        # defined, before the fall-back anonymous handler, even if this
        # profile does not have credentials.
        handler_defs.append(
            {
                "name": resource["name"],
                "handler_name": handler_command_name(resource["name"]),
                "actions": list(actions.values()),
                **(resource["auth"] or resource["anon"]),
            }
        )

    for handler in sorted(handler_defs, key=itemgetter("handler_name")):
        register_handler(profile, handler, parser)


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
profile_help = "\n\n".join(
    fill(dedent(paragraph)) for paragraph in profile_help_paragraphs
)


def register_api_commands(parser):
    """Register all profiles as subcommands on `parser`."""
    with suppress(FileNotFoundError), ProfileConfig.open() as config:
        for profile_name in config:
            profile = config[profile_name]
            profile_parser = parser.subparsers.add_parser(
                profile["name"],
                help="Interact with %(url)s" % profile,
                description=(
                    "Issue commands to the MAAS region controller at "
                    "%(url)s." % profile
                ),
                epilog=profile_help,
            )
            register_resources(profile, profile_parser)


def materialize_certificate(profile, cert_dir="~/.maascli.certs"):
    """Create CA certificate file, from profile config data.

    This will take CA certificates data stored in user profile
    and create a file <profile>.pem under ~/.maascli.certs
    File is needed for httplib2 ca_cert (for server cert validation)
    """

    profile_name = profile.get("name")
    if profile_name is None:
        return None

    cert_path = Path(cert_dir).expanduser() / (profile_name + ".pem")

    if cert_path.exists():
        return cert_path

    cacerts = profile.get("cacerts")
    if cacerts is None:
        return None

    cert_path.parent.mkdir(exist_ok=True, parents=True)
    cert_path.write_text(cacerts)

    return cert_path

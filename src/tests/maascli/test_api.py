# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from argparse import Namespace
from base64 import b64encode
from functools import partial
import http.client
import json
from pathlib import Path
import sys
import tempfile
from textwrap import dedent
from unittest.mock import Mock, sentinel
from urllib.parse import parse_qs, urlparse

import httplib2
import pytest

from maascli import api, utils
from maascli.actions.boot_resources_create import BootResourcesCreateAction
from maascli.actions.sshkeys_import import SSHKeysImportAction
from maascli.command import CommandError
from maascli.config import ProfileConfig
from maascli.parser import ArgumentParser, get_deepest_subparser
from maascli.testing.config import make_configs, make_profile
from maascli.utils import handler_command_name, safe_name
from maastesting.factory import factory
from maastesting.fixtures import CaptureStandardIO
from maastesting.testcase import MAASTestCase
from provisioningserver.testing.certificates import get_sample_cert


class TestRegisterAPICommands(MAASTestCase):
    """Tests for `register_api_commands`."""

    def make_profile(self):
        """Fake a profile."""
        self.patch(ProfileConfig, "open").return_value = make_configs()
        return ProfileConfig.open.return_value

    def test_registers_subparsers(self):
        profile_name = list(self.make_profile().keys())[0]
        parser = ArgumentParser()
        self.assertIsNone(parser._subparsers)
        api.register_api_commands(parser)
        self.assertIsNotNone(parser._subparsers)
        self.assertIsNotNone(parser.subparsers.choices[profile_name])

    def test_handlers_registered_using_correct_names(self):
        profile = self.make_profile()
        parser = ArgumentParser()
        api.register_api_commands(parser)
        for resource in list(profile.values())[0]["description"]["resources"]:
            for action in resource["auth"]["actions"]:
                # Profile names are matched as-is.
                [profile_name] = profile
                # Handler names are processed with handler_command_name before
                # being added to the argument parser tree.
                handler_name = handler_command_name(resource["name"])
                # Action names are processed with safe_name before being added
                # to the argument parser tree.
                action_name = safe_name(action["name"])
                # Parsing these names as command-line arguments yields an
                # options object. Its execute attribute is an instance of
                # Action (or a subclass thereof).
                options = parser.parse_args(
                    (profile_name, handler_name, action_name)
                )
                self.assertIsInstance(options.execute, api.Action)

    def test_parser_includes_data_arg(self):
        profile = self.make_profile()
        profile_name = list(profile.keys())[0]
        parser = ArgumentParser()
        api.register_api_commands(parser)
        # the first resource should have an action with a data param
        resource = list(profile.values())[0]["description"]["resources"][0]
        handler_name = handler_command_name(resource["name"])
        # get the action with a data param
        action = next(
            x for x in resource["auth"]["actions"] if "data" in x["name"]
        )
        action_name = safe_name(action["name"])
        subparser = get_deepest_subparser(
            parser, [profile_name, handler_name, action_name]
        )
        positional_action_names = [
            x.dest for x in subparser._get_positional_actions()
        ]
        self.assertIn("data", positional_action_names)

    def test_parser_omits_data_arg(self):
        profile = self.make_profile()
        profile_name = list(profile.keys())[0]
        parser = ArgumentParser()
        api.register_api_commands(parser)
        # the first resource should have an action with a data param
        resource = list(profile.values())[0]["description"]["resources"][0]
        handler_name = handler_command_name(resource["name"])
        # get the action without a data param
        action = next(
            x for x in resource["auth"]["actions"] if "data" not in x["name"]
        )
        action_name = safe_name(action["name"])
        subparser = get_deepest_subparser(
            parser, [profile_name, handler_name, action_name]
        )
        positional_action_names = [
            x.dest for x in subparser._get_positional_actions()
        ]
        self.assertNotIn("data", positional_action_names)


class TestFunctions(MAASTestCase):
    """Test for miscellaneous functions in `maascli.api`."""

    def test_fetch_api_description(self):
        content = factory.make_name("content")
        request = self.patch(httplib2.Http, "request")
        response = httplib2.Response({})
        response.status = http.client.OK
        response["content-type"] = "application/json"
        request.return_value = response, bytes(json.dumps(content), "utf-8")
        self.assertEqual(
            content, api.fetch_api_description("http://example.com/api/2.0/")
        )
        request.assert_called_once_with(
            "http://example.com/api/2.0/describe/",
            "GET",
            body=None,
            headers=None,
        )

    def test_fetch_api_description_not_okay(self):
        # If the response is not 200 OK, fetch_api_description throws toys.
        content = factory.make_name("content")
        request = self.patch(httplib2.Http, "request")
        response = httplib2.Response({})
        response.status = http.client.BAD_REQUEST
        response.reason = http.client.responses[http.client.BAD_REQUEST]
        request.return_value = response, json.dumps(content)
        error = self.assertRaises(
            CommandError,
            api.fetch_api_description,
            "http://example.com/api/2.0/",
        )
        error_expected = "%d %s:\n%s" % (
            http.client.BAD_REQUEST,
            http.client.responses[http.client.BAD_REQUEST],
            json.dumps(content),
        )
        self.assertEqual(error_expected, "%s" % error)

    def test_fetch_api_description_wrong_content_type(self):
        # If the response's content type is not application/json,
        # fetch_api_description throws toys again.
        content = factory.make_name("content")
        request = self.patch(httplib2.Http, "request")
        response = httplib2.Response({})
        response.status = http.client.OK
        response["content-type"] = "text/css"
        request.return_value = response, json.dumps(content)
        error = self.assertRaises(
            CommandError,
            api.fetch_api_description,
            "http://example.com/api/2.0/",
        )
        self.assertEqual(
            "Expected application/json, got: text/css", "%s" % error
        )

    def test_http_request_raises_error_if_cert_verify_fails(self):
        self.patch(
            httplib2.Http,
            "request",
            Mock(
                side_effect=httplib2.ssl.SSLError(
                    997,
                    "ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]",
                )
            ),
        )
        error = self.assertRaises(
            CommandError,
            api.http_request,
            factory.make_name("fake_url"),
            factory.make_name("fake_method"),
        )
        error_expected = (
            "Certificate verification failed, use --insecure/-k to "
            "disable the certificate check.\n"
            "ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED]"
        )
        self.assertEqual(error_expected, "%s" % error)

    def test_get_action_class_returns_None_for_unknown_handler(self):
        handler = {
            "name": factory.make_name("handler"),
            "handler_name": factory.make_name("handler"),
        }
        action = {"name": "create"}
        self.assertIsNone(api.get_action_class(handler, action))

    def test_get_action_class_returns_BootResourcesCreateAction_class(self):
        # Test uses BootResourcesCreateAction as its know to exist.
        handler = {
            "name": "BootResourcesHandler",
            "handler_name": "boot-resources",
        }
        action = {"name": "create"}
        self.assertEqual(
            BootResourcesCreateAction, api.get_action_class(handler, action)
        )

    def test_get_action_class_returns_SSHKeysImportAction_class(self):
        # Test uses SSHKeysImportAction as its know to exist.
        handler = {"name": "SSHKeysHandler", "handler_name": "sshkeys"}
        action = {"name": "import"}
        self.assertEqual(
            SSHKeysImportAction, api.get_action_class(handler, action)
        )

    def test_get_action_class_bases_returns_Action(self):
        handler = {
            "name": factory.make_name("handler"),
            "handler_name": factory.make_name("handler"),
        }
        action = {"name": "create"}
        self.assertEqual(
            (api.Action,), api.get_action_class_bases(handler, action)
        )

    def test_get_action_class_bases_returns_BootResourcesCreateAction(self):
        # Test uses BootResourcesCreateAction as its know to exist.
        handler = {
            "name": "BootResourcesHandler",
            "handler_name": "boot-resources",
        }
        action = {"name": "create"}
        self.assertEqual(
            (BootResourcesCreateAction,),
            api.get_action_class_bases(handler, action),
        )

    def test_get_action_class_bases_returns_SSHKeysImportAction(self):
        # Test uses SSHKeysImportAction as its know to exist.
        handler = {"name": "SSHKeysHandler", "handler_name": "sshkeys"}
        action = {"name": "import"}
        self.assertEqual(
            (SSHKeysImportAction,), api.get_action_class_bases(handler, action)
        )

    def test_materialize_certificate_profile_no_cacerts(self):
        profile = make_profile()
        self.assertIsNone(api.materialize_certificate(profile))

    def test_materialize_certificate_profile_cacerts_is_none(self):
        profile = make_profile()
        profile["cacerts"] = None
        self.assertIsNone(api.materialize_certificate(profile))

    def test_materialize_certificate_creates_cacert_file(self):
        profile = make_profile()
        sample_cert = get_sample_cert()
        cert = sample_cert.certificate_pem()
        profile["cacerts"] = cert
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            api.materialize_certificate(profile, tmp)
            cert_path = temp_dir = temp_dir / (profile["name"] + ".pem")
            self.assertEqual(cert, cert_path.open().read())

    def test_materialize_certificate_should_return_existing_cert(self):
        mock_write_cert = self.patch(Path, "write_text")
        profile = make_profile()
        with tempfile.TemporaryDirectory() as tmp:
            cert_file = Path(tmp) / (profile["name"] + ".pem")
            cert_file.touch()
            self.assertEqual(
                cert_file, api.materialize_certificate(profile, tmp)
            )
            mock_write_cert.assert_not_called()


class TestAction(MAASTestCase):
    """Tests for :class:`maascli.api.Action`."""

    def test_name_value_pair_returns_2_tuple(self):
        # The tuple is important because this is used as input to
        # urllib.urlencode, which doesn't let the data it consumes walk and
        # quack like a duck. It insists that the first item in a non-dict
        # sequence is a tuple. Of any size. It does this in the name of
        # avoiding *string* input.
        result = api.Action.name_value_pair("foo=bar")
        self.assertEqual(result, ("foo", "bar"))

    def test_name_value_pair_demands_two_parts(self):
        self.assertRaises(CommandError, api.Action.name_value_pair, "foo bar")

    def test_name_value_pair_does_not_strip_whitespace(self):
        self.assertEqual(
            (" foo ", " bar "), api.Action.name_value_pair(" foo = bar ")
        )

    def test_compare_api_hashes_prints_nothing_if_hashes_match(self):
        example_hash = factory.make_name("hash")
        profile = {"description": {"hash": example_hash}}
        response = {"x-maas-api-hash": example_hash}
        with CaptureStandardIO() as stdio:
            api.Action.compare_api_hashes(profile, response)
        self.assertEqual(stdio.getOutput(), "")
        self.assertEqual(stdio.getError(), "")

    def test_compare_api_hashes_prints_nothing_if_remote_has_no_hash(self):
        example_hash = factory.make_name("hash")
        profile = {"description": {"hash": example_hash}}
        response = {}
        with CaptureStandardIO() as stdio:
            api.Action.compare_api_hashes(profile, response)
        self.assertEqual(stdio.getOutput(), "")
        self.assertEqual(stdio.getError(), "")

    def test_compare_api_hashes_prints_warning_if_local_has_no_hash(self):
        example_hash = factory.make_name("hash")
        profile = {"description": {}}
        response = {"x-maas-api-hash": example_hash}
        with CaptureStandardIO() as stdio:
            api.Action.compare_api_hashes(profile, response)
        self.assertEqual(stdio.getOutput(), "")
        self.assertEqual(
            stdio.getError(),
            dedent(
                """\
        **********************************************************************
        *** WARNING! The API on the server differs from the description that
        *** is cached locally. This may result in failed API calls. Refresh
        *** the local API description with `maas refresh`.
        **********************************************************************
        """
            ),
        )

    def test_compare_api_hashes_prints_warning_if_hashes_dont_match(self):
        example_hash = factory.make_name("hash")
        profile = {"description": {"hash": example_hash + "foo"}}
        response = {"x-maas-api-hash": example_hash + "bar"}
        with CaptureStandardIO() as stdio:
            api.Action.compare_api_hashes(profile, response)
        self.assertEqual(stdio.getOutput(), "")
        self.assertEqual(
            stdio.getError(),
            dedent(
                """\
        **********************************************************************
        *** WARNING! The API on the server differs from the description that
        *** is cached locally. This may result in failed API calls. Refresh
        *** the local API description with `maas refresh`.
        **********************************************************************
                """
            ),
        )

    def test_action_call_materialize_certificate(self):
        handler = {
            "name": factory.make_name("handler"),
            "handler_name": factory.make_name("handler"),
            "params": [],
            "path": "/MAAS/api/2.0",
            "uri": "http://example.com/MAAS/api/2.0/",
        }
        action = {"name": "action", "op": "test", "method": "GET"}
        action_name = safe_name(action["name"])
        action_bases = api.get_action_class_bases(handler, action)
        profile = make_profile()
        profile["credentials"] = None

        action_ns = {"action": action, "handler": handler, "profile": profile}
        action_class = type(action_name, action_bases, action_ns)

        parser = ArgumentParser()
        action_parser = action_class(parser)

        options = Namespace(
            insecure=False,
            cacerts=None,
            data={},
            debug=False,
        )

        response = httplib2.Response(
            {
                "content-type": "application/json",
                "status": "200",
                "content-length": 0,
            }
        )

        self.patch(api, "http_request").return_value = (response, {})
        mock_materializer = self.patch(api, "materialize_certificate")
        mock_materializer.return_value = None

        self.patch(action_parser, "compare_api_hashes").return_value = None
        self.patch(utils, "print_response_content")
        action_parser(options)
        mock_materializer.assert_called_once()

    def test_action_build_correct_uri(self):
        handler = {
            "name": factory.make_name("handler"),
            "handler_name": factory.make_name("handler"),
            "params": [],
            "path": "/MAAS/api/2.0/resource",
        }
        action = {"name": "action", "op": "test", "method": "GET"}
        action_name = safe_name(action["name"])
        action_bases = api.get_action_class_bases(handler, action)
        profile = make_profile()
        profile["url"] = "http://localhost:5240/MAAS"

        action_ns = {"action": action, "handler": handler, "profile": profile}
        action_class = type(action_name, action_bases, action_ns)

        parser = ArgumentParser()
        action_parser = action_class(parser)

        self.assertEqual(
            "http://localhost:5240/MAAS/api/2.0/resource", action_parser.uri
        )


class TestActionHelp(MAASTestCase):
    def make_help(self):
        """Create an `ActionHelp` object."""
        option_strings = []
        dest = "arg"
        return api.ActionHelp(option_strings, dest)

    def make_namespace(self):
        """Return a `namespace` argument that `argparse.Action` will accept."""
        return factory.make_name("namespace")

    def make_values(self):
        """Return a `values` argument that `argparse.Action` will accept."""
        return []

    def make_option_string(self):
        """Return an `options_string` that `argparse.Action` will accept."""
        return ""

    def test_get_positional_args_returns_empty_list_if_no_args(self):
        self.assertEqual(
            [], api.ActionHelp.get_positional_args(ArgumentParser())
        )

    def test_get_positional_args_lists_arguments(self):
        option = factory.make_name("opt", sep="_")
        parser = ArgumentParser()
        parser.add_argument(option)
        self.assertEqual([option], api.ActionHelp.get_positional_args(parser))

    def test_get_positional_args_omits_final_data_arg(self):
        parser = ArgumentParser()
        option = factory.make_name("opt", sep="_")
        parser.add_argument(option)
        parser.add_argument("data")
        self.assertEqual([option], api.ActionHelp.get_positional_args(parser))

    def test_get_positional_args_includes_other_arg(self):
        parser = ArgumentParser()
        parser.add_argument("data")
        option = factory.make_name("opt", sep="_")
        parser.add_argument(option)
        self.assertEqual(
            ["data", option], api.ActionHelp.get_positional_args(parser)
        )

    def test_get_positional_args_returns_empty_if_data_is_only_arg(self):
        parser = ArgumentParser()
        parser.add_argument("data")
        self.assertEqual([], api.ActionHelp.get_positional_args(parser))

    def test_get_positional_args_ignores_optional_args(self):
        parser = ArgumentParser()
        parser.add_argument("--option")
        self.assertEqual([], api.ActionHelp.get_positional_args(parser))

    def test_get_optional_args_returns_empty_if_no_args(self):
        self.assertEqual(
            [],
            api.ActionHelp.get_optional_args(ArgumentParser(add_help=False)),
        )

    def test_get_optional_args_returns_optional_args(self):
        option = "--%s" % factory.make_name("opt")
        parser = ArgumentParser(add_help=False)
        parser.add_argument(option)
        args = api.ActionHelp.get_optional_args(parser)
        self.assertEqual(
            [[option]], [action.option_strings for action in args]
        )

    def test_compose_positional_args_returns_empty_if_no_args(self):
        self.assertEqual(
            [], api.ActionHelp.compose_positional_args(ArgumentParser())
        )

    def test_compose_positional_args_describes_positional_args(self):
        arg = factory.make_name("arg", sep="_")
        parser = ArgumentParser()
        parser.add_argument(arg)
        self.assertEqual(
            dedent(
                """\


                Positional arguments:
                \t%s
                """.rstrip()
            )
            % arg,
            "\n".join(api.ActionHelp.compose_positional_args(parser)),
        )

    def test_compose_positional_args_does_not_end_with_newline(self):
        arg = factory.make_name("arg", sep="_")
        parser = ArgumentParser()
        parser.add_argument(arg)
        self.assertFalse(
            "\n".join(api.ActionHelp.compose_positional_args(parser)).endswith(
                "\n"
            )
        )

    def test_compose_epilog_returns_empty_if_no_epilog(self):
        self.assertEqual([], api.ActionHelp.compose_epilog(ArgumentParser()))

    def test_compose_epilog_returns_empty_if_epilog_is_empty(self):
        self.assertEqual(
            [], api.ActionHelp.compose_epilog(ArgumentParser(epilog=""))
        )

    def test_compose_epilog_returns_empty_if_epilog_is_whitespace(self):
        self.assertEqual(
            [], api.ActionHelp.compose_epilog(ArgumentParser(epilog="  \n"))
        )

    def test_compose_epilog_returns_epilog(self):
        epilog = factory.make_name("epi")
        self.assertEqual(
            "\n\n%s" % epilog,
            "\n".join(
                api.ActionHelp.compose_epilog(ArgumentParser(epilog=epilog))
            ),
        )

    def test_compose_epilog_preserves_indentation(self):
        indent = " " * 8
        epilog = indent + factory.make_name("epi")
        self.assertEqual(
            "\n\n%s" % epilog,
            "\n".join(
                api.ActionHelp.compose_epilog(ArgumentParser(epilog=epilog))
            ),
        )

    def test_compose_epilog_explains_documented_keyword_args(self):
        epilog = ":param foo: The amount of foo."
        self.assertEqual(
            f"\n\n{api.ActionHelp.keyword_args_help}\n{epilog}",
            "\n".join(
                api.ActionHelp.compose_epilog(ArgumentParser(epilog=epilog))
            ),
        )

    def test_compose_optional_args_returns_empty_if_none_defined(self):
        self.assertEqual(
            [],
            api.ActionHelp.compose_optional_args(
                ArgumentParser(add_help=False)
            ),
        )

    def test_compose_optional_args_describes_optional_args(self):
        long_option = "--%s" % factory.make_name("opt", sep="_")
        short_option = "-o"
        option_help = factory.make_name("help")
        parser = ArgumentParser(add_help=False)
        parser.add_argument(long_option, short_option, help=option_help)
        expected_text = (
            dedent(
                """\


            Common command-line options:
                %s
            \t%s
            """
            )
            % (", ".join([long_option, short_option]), option_help)
        )
        self.assertEqual(
            expected_text.rstrip(),
            "\n".join(api.ActionHelp.compose_optional_args(parser)),
        )

    def test_compose_shows_at_least_usage_and_description(self):
        usage = factory.make_name("usage")
        description = factory.make_name("description")
        parser = ArgumentParser(
            usage=usage, description=description, add_help=False
        )
        self.assertEqual(
            dedent(
                """\
                usage: %s

                %s
                """
            ).rstrip()
            % (usage, description),
            api.ActionHelp.compose(parser),
        )

    def test_call_exits(self):
        parser = ArgumentParser(description=factory.make_string())
        action_help = self.make_help()
        self.patch(sys, "exit")
        self.patch(api, "print")
        action_help(
            parser,
            self.make_namespace(),
            self.make_values(),
            self.make_option_string(),
        )
        sys.exit.assert_called_once_with(0)

    def test_call_shows_full_enchilada(self):
        usage = factory.make_name("usage")
        description = factory.make_name("description")
        epilog = dedent(
            """\
            More detailed description here.
            Typically more than one line.
            :param foo: The amount of foo.
            """
        ).rstrip()
        arg = factory.make_name("arg", sep="_")
        parser = ArgumentParser(
            usage=usage, description=description, epilog=epilog, add_help=False
        )
        parser.add_argument(arg)
        option = "--%s" % factory.make_name("opt")
        option_help = factory.make_name("help")
        parser.add_argument(option, help=option_help)
        params = {
            "usage": usage,
            "description": description,
            "arg": arg,
            "keyword_args_help": api.ActionHelp.keyword_args_help.rstrip(),
            "epilog": epilog,
            "option": option,
            "option_help": option_help,
        }
        expected_text = (
            dedent(
                """\
            usage: %(usage)s

            %(description)s


            Positional arguments:
            \t%(arg)s


            %(keyword_args_help)s

            %(epilog)s


            Common command-line options:
                %(option)s
            \t%(option_help)s
            """
            ).rstrip()
            % params
        )
        action_help = self.make_help()
        self.patch(sys, "exit")
        self.patch(api, "print")

        # Invoke ActionHelp.__call__, so we can see what it prints.
        action_help(
            parser,
            self.make_namespace(),
            self.make_values(),
            self.make_option_string(),
        )

        api.print.assert_called_once_with(expected_text)


class TestPayloadPreparation:
    @pytest.mark.parametrize(
        "op,method,data,expected_querystring,expected_body,expected_headers",
        [
            # ReSTful operations; i.e. without an "op" parameter.
            #
            # Without data, all requests have an empty request body and no
            # extra headers.
            (None, "POST", [], "", None, []),
            (None, "GET", [], "", None, []),
            (None, "PUT", [], "", None, []),
            (None, "DELETE", [], "", None, []),
            # With data, PUT, POST, and DELETE requests have their body and
            # extra headers prepared by build_multipart_message and
            # encode_multipart_message. For GET requests, the data is encoded
            # into the query string, and both the request body and extra
            # headers are empty.
            (
                None,
                "POST",
                [("foo", "bar"), ("foo", "baz")],
                "",
                sentinel.body,
                sentinel.headers,
            ),
            (
                None,
                "GET",
                [("foo", "bar"), ("foo", "baz")],
                "?foo=bar&foo=baz",
                None,
                [],
            ),
            (
                None,
                "PUT",
                [("foo", "bar"), ("foo", "baz")],
                "",
                sentinel.body,
                sentinel.headers,
            ),
            (
                None,
                "DELETE",
                [("foo", "bar"), ("foo", "baz")],
                "?foo=bar&foo=baz",
                None,
                [],
            ),
            #
            # non-ReSTful operations; i.e. with an "op" parameter.
            #
            # Without data, all requests have an empty request body and no extra
            # headers. The operation is encoded into the query string.
            ("something", "POST", [], "?op=something", None, []),
            ("something", "GET", [], "?op=something", None, []),
            ("something", "PUT", [], "?op=something", None, []),
            ("something", "DELETE", [], "?op=something", None, []),
            # With data, PUT, POST, and DELETE requests have their body and
            # extra headers prepared by build_multipart_message and
            # encode_multipart_message. For GET requests, the data is encoded
            # into the query string, and both the request body and extra
            # headers are empty. The operation is encoded into the query
            # string.
            (
                "something",
                "POST",
                [("foo", "bar"), ("foo", "baz")],
                "?op=something",
                sentinel.body,
                sentinel.headers,
            ),
            (
                "something",
                "GET",
                [("foo", "bar"), ("foo", "baz")],
                "?op=something&foo=bar&foo=baz",
                None,
                [],
            ),
            (
                "something",
                "PUT",
                [("foo", "bar"), ("foo", "baz")],
                "?op=something",
                sentinel.body,
                sentinel.headers,
            ),
            (
                "something",
                "DELETE",
                [("foo", "bar"), ("foo", "baz")],
                "?op=something&foo=bar&foo=baz",
                None,
                [],
            ),
        ],
    )
    def test_prepare_payload(
        self,
        mocker,
        op,
        method,
        data,
        expected_querystring,
        expected_body,
        expected_headers,
    ):
        build_multipart_message = mocker.patch.object(
            api, "build_multipart_message"
        )
        build_multipart_message.return_value = sentinel.message
        encode_multipart_message = mocker.patch.object(
            api, "encode_multipart_message"
        )
        encode_multipart_message.return_value = sentinel.headers, sentinel.body
        # The payload returned is a 3-tuple of (uri, body, headers).
        payload = api.Action.prepare_payload(
            op=op,
            method=method,
            uri="http://example.com/MAAS/api/2.0/",
            data=data,
        )
        assert payload == (
            f"http://example.com/MAAS/api/2.0/{expected_querystring}",
            expected_body,
            expected_headers,
        )
        # encode_multipart_message, when called, is passed the data
        # unadulterated.
        if expected_body is sentinel.body:
            build_multipart_message.assert_called_once_with(data)
            encode_multipart_message.assert_called_once_with(sentinel.message)


class TestPayloadPreparationWithFiles:
    """Tests for `maascli.api.Action.prepare_payload` involving files."""

    def make_data(self, tmpdir, binary=True):
        parameter = factory.make_name("param")
        payload_file = tmpdir / "payload.file"
        if binary:
            contents = factory.make_bytes()
            payload_file.write_binary(contents)
        else:
            contents = factory.make_string()
            payload_file.write_text(contents, "ascii")
        # Writing the parameter as "parameter@=filename" on the
        # command-line causes name_value_pair() to return a `name,
        # opener` tuple, where `opener` is a callable that returns an
        # open file handle.
        data = [(parameter, partial(payload_file.open, "rb"))]
        return parameter, contents, data

    @pytest.mark.parametrize("op", [None, "action"])
    def test_files_are_included_post(self, tmpdir, op):
        parameter, contents, data = self.make_data(tmpdir)
        uri, body, headers = api.Action.prepare_payload(
            op=op, method="POST", uri="http://localhost", data=data
        )

        query = parse_qs(urlparse(uri).query)
        if op:
            assert query["op"] == [op]
        else:
            assert query == {}

        content_lines = [
            "Content-Type: application/octet-stream",
            "MIME-Version: 1.0",
            "Content-Transfer-Encoding: base64",
            f'Content-Disposition: form-data; name="{parameter}"; filename="{parameter}"',
            b64encode(contents).decode("ascii"),
        ]
        for line in content_lines:
            assert line + "\r\n" in body

    @pytest.mark.parametrize("op", [None, "action"])
    def test_files_are_included_get(self, tmpdir, op):
        parameter, contents, data = self.make_data(tmpdir, binary=False)
        uri, body, headers = api.Action.prepare_payload(
            op=op, method="GET", uri="http://localhost", data=data
        )

        assert body is None

        query = parse_qs(urlparse(uri).query)
        if op:
            assert query["op"] == [op]

        assert query[parameter] == [contents]

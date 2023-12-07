# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the subcommand utilities."""


from argparse import ArgumentParser, Namespace
from random import randint
from subprocess import CalledProcessError
import types

from maastesting.factory import factory
from maastesting.fixtures import CaptureStandardIO
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import script as script_module
from provisioningserver.utils.script import ActionScript, ActionScriptError


class TestActionScript(MAASTestCase):
    """Test `ActionScript`."""

    factory = ActionScript

    def setUp(self):
        super().setUp()
        # ActionScript.setup() is not safe to run in the test suite.
        self.patch(ActionScript, "setup", lambda self: None)
        # ArgumentParser sometimes likes to print to stdout/err.
        self.stdio = self.useFixture(CaptureStandardIO())

    def test_init(self):
        description = factory.make_string()
        script = self.factory(description)
        self.assertIsInstance(script.parser, ArgumentParser)
        self.assertEqual(description, script.parser.description)

    def test_register(self):
        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: (
            self.assertIsInstance(parser, ArgumentParser)
        )
        handler.run = lambda args: (self.assertIsInstance(args, int))
        script = self.factory("Description")
        script.register("slay", handler)
        self.assertIn("slay", script.subparsers.choices)
        action_parser = script.subparsers.choices["slay"]
        self.assertIsInstance(action_parser, ArgumentParser)

    def test_register_without_add_arguments(self):
        # ActionScript.register will crash if the handler has no
        # add_arguments() callable.
        handler = types.ModuleType("handler")
        handler.run = lambda args: None
        script = self.factory("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler
        )
        self.assertIn("'add_arguments'", "%s" % error)

    def test_register_without_run(self):
        # ActionScript.register will crash if the handler has no run()
        # callable.
        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        script = self.factory("Description")
        error = self.assertRaises(
            AttributeError, script.register, "decapitate", handler
        )
        self.assertIn("'run'", "%s" % error)

    def test_call(self):
        handler_calls = []
        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        handler.run = handler_calls.append
        script = self.factory("Description")
        script.register("amputate", handler)
        error = self.assertRaises(SystemExit, script, ["amputate"])
        self.assertEqual(0, error.code)
        self.assertEqual(1, len(handler_calls))
        self.assertIsInstance(handler_calls[0], Namespace)

    def test_call_invalid_choice(self):
        script = self.factory("Description")
        self.assertRaises(SystemExit, script, ["disembowel"])
        self.assertIn("invalid choice", self.stdio.getError())

    def test_call_with_exception(self):
        # Most exceptions from run() are propagated.
        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: 0 / 0
        script = self.factory("Description")
        script.register("eviscerate", handler)
        self.assertRaises(ZeroDivisionError, script, ["eviscerate"])

    def test_call_with_process_exception(self):
        # CalledProcessError is converted into SystemExit.
        exception = CalledProcessError(
            randint(0, 256),
            [factory.make_string()],
            factory.make_string().encode("ascii"),
        )

        def raise_exception():
            raise exception

        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: raise_exception()
        script = self.factory("Description")
        script.register("sever", handler)
        error = self.assertRaises(SystemExit, script, ["sever"])
        self.assertEqual(exception.returncode, error.code)

    def test_call_with_keyboard_interrupt(self):
        # KeyboardInterrupt is silently converted into SystemExit, with an
        # exit code of 1.

        def raise_exception():
            raise KeyboardInterrupt()

        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: raise_exception()
        script = self.factory("Description")
        script.register("smash", handler)
        error = self.assertRaises(SystemExit, script, ["smash"])
        self.assertEqual(1, error.code)

    def test_call_with_actionscripterror(self):
        # ActionScriptError is converted into SystemExit, with  the
        # specified exit code. (And the message is printed to stderr.)

        def raise_exception():
            raise ActionScriptError("Towel.", returncode=42)

        handler = types.ModuleType("handler")
        handler.add_arguments = lambda parser: None
        handler.run = lambda args: raise_exception()
        script = self.factory("Description")
        script.register("smash", handler)
        with self.assertRaisesRegex(SystemExit, "42"):
            # This needs to be a no-op.
            self.patch(script_module.ActionScript, "setup")
            script(["smash"])
        self.assertEqual("Towel.\n", self.stdio.getError())

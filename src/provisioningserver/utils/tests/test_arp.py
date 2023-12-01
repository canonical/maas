# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.arp``."""


from argparse import ArgumentParser
import io
from unittest.mock import Mock

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import arp as arp_module
from provisioningserver.utils.arp import add_arguments, run
from provisioningserver.utils.script import ActionScriptError


class TestObserveARPCommand(MAASTestCase):
    """Tests for `maas-rack observe-arp`."""

    def test_requires_input_interface(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args([])
        with self.assertRaisesRegex(
            ActionScriptError, "Required argument: interface"
        ):
            run(args)

    def test_calls_subprocess_for_interface(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["eth0"])
        popen = self.patch(arp_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.StringIO("{}")
        output = io.StringIO()
        run(args, output=output)
        popen.assert_called_once_with(
            ["sudo", "-n", "/usr/sbin/maas-netmon", "eth0"], stdout=output
        )

    def test_calls_subprocess_for_interface_sudo(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["eth0"])
        popen = self.patch(arp_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.StringIO("{}")
        output = io.StringIO()
        run(args, output=output)
        popen.assert_called_once_with(
            ["sudo", "-n", "/usr/sbin/maas-netmon", "eth0"], stdout=output
        )

    def test_raises_systemexit_poll_result(self):
        parser = ArgumentParser()
        add_arguments(parser)
        args = parser.parse_args(["eth0"])
        popen = self.patch(arp_module.subprocess, "Popen")
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = None
        popen.return_value.stdout = io.StringIO("{}")
        output = io.StringIO()
        observe_arp_packets = self.patch(arp_module, "observe_arp_packets")
        observe_arp_packets.return_value = None
        popen.return_value.poll = Mock()
        popen.return_value.poll.return_value = 42
        with self.assertRaisesRegex(SystemExit, "42"):
            run(args, output=output)

    def test_sets_self_as_process_group_leader(self):
        exception_type = factory.make_exception_type()
        os = self.patch(arp_module, "os")
        os.setpgrp.side_effect = exception_type
        self.assertRaises(exception_type, run, [])
        os.setpgrp.assert_called_once_with()

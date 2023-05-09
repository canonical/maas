# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for ``provisioningserver.utils.arp``."""


from argparse import ArgumentParser
import io
from unittest.mock import Mock

from testtools.testcase import ExpectedException

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
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
        with ExpectedException(
            ActionScriptError, ".*Required argument: interface.*"
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
        self.assertThat(
            popen,
            MockCalledOnceWith(
                ["sudo", "-n", "/usr/sbin/maas-netmon", "eth0"], stdout=output
            ),
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
        self.assertThat(
            popen,
            MockCalledOnceWith(
                ["sudo", "-n", "/usr/sbin/maas-netmon", "eth0"], stdout=output
            ),
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
        with ExpectedException(SystemExit, ".*42.*"):
            run(args, output=output)

    def test_sets_self_as_process_group_leader(self):
        exception_type = factory.make_exception_type()
        os = self.patch(arp_module, "os")
        os.setpgrp.side_effect = exception_type
        self.assertRaises(exception_type, run, [])
        self.assertThat(os.setpgrp, MockCalledOnceWith())

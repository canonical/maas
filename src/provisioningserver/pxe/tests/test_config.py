# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.pxe.config`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver.pxe.config import render_pxe_config
from testtools.matchers import (
    Contains,
    IsInstance,
    MatchesAll,
    StartsWith,
    )


class TestRenderPXEConfig(TestCase):
    """Tests for `provisioningserver.pxe.config.render_pxe_config`."""

    def test_render(self):
        # Given the right configuration options, the PXE configuration is
        # correctly rendered.
        options = {
            "title": factory.make_name("title"),
            "kernel": factory.make_name("kernel"),
            "initrd": factory.make_name("initrd"),
            "append": factory.make_name("append"),
            }
        output = render_pxe_config(**options)
        # The output is always a Unicode string.
        self.assertThat(output, IsInstance(unicode))
        # The template has rendered without error. PXELINUX configurations
        # typically start with a DEFAULT line.
        self.assertThat(output, StartsWith("DEFAULT "))
        # All of the values put in are included somewhere in the output.
        expected = (Contains(value) for value in options.values())
        self.assertThat(output, MatchesAll(*expected))

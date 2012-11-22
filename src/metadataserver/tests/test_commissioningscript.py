# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commissioning scripts."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import codecs
from random import randint

from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from metadataserver.fields import Bin
from metadataserver.models import CommissioningScript


def make_script_name(base_name=None, number=None):
    """Make up a name for a commissioning script."""
    if base_name is None:
        base_name = 'script'
    if number is None:
        number = randint(0, 99)
    return factory.make_name(
        '%0.2d-%s' % (number, factory.make_name(base_name)))


class TestCommissioningScript(TestCase):

    def test_scripts_may_be_binary(self):
        name = make_script_name()
        # Some binary data that would break just about any kind of text
        # interpretation.
        binary = Bin(codecs.BOM64_LE + codecs.BOM64_BE + b'\x00\xff\x00')
        CommissioningScript.objects.create(name=name, content=binary)
        stored_script = CommissioningScript.objects.get(name=name)
        self.assertEqual(binary, stored_script.content)

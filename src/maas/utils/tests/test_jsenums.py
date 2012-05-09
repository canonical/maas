# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maas.utils.jsenums`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from inspect import getsourcefile

from maas.utils.jsenums import (
    dump,
    footer,
    get_enums,
    header,
    serialize_enum,
    )
from maasserver.utils import map_enum
from maastesting.testcase import TestCase


class ENUM:
    ALICE = 1
    BOB = 2


class TestFunctions(TestCase):

    def test_serialize_enum(self):
        # The name is used correctly, the keys are sorted, and everything is
        # indented correctly.
        self.assertEqual(
            'module.ENUM = {\n'
            '    "ALICE": 1, \n'
            '    "BOB": 2\n'
            '};\n',
            serialize_enum(ENUM))

    def test_get_enums(self):
        # This file contains a single enum, named "ENUM".
        enums = get_enums(getsourcefile(TestFunctions))
        self.assertEqual(["ENUM"], [enum.__name__ for enum in enums])
        [enum] = enums
        # Because the module has been executed in a different namespace, the
        # enum we've found is not the same object as the one in the current
        # global namespace.
        self.assertIsNot(ENUM, enum)
        # It does, however, have the same values.
        self.assertEqual(map_enum(ENUM), map_enum(enum))

    def test_dump(self):
        self.assertEqual(header + "\n" + footer, dump([]))
        self.assertEqual(
            header + "\n" + serialize_enum(ENUM) + "\n" + footer,
            dump([getsourcefile(TestFunctions)]))

# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test :class:`Sequence`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import random

from django.db import connection
from django.db.utils import DatabaseError
from maasserver.sequence import Sequence
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase


class TestSequence(TestCase):

    def query_seq(self, name):
        cursor = connection.cursor()
        cursor.execute(
            "SELECT nextval(%s)", [name])
        return cursor.fetchone()[0]

    def test_create_sequence(self):
        name = factory.make_name('seq', sep='')
        seq = Sequence(name)
        seq.create()
        val = self.query_seq(seq.name)
        self.assertEqual(1, val)

    def test_sequence_respects_minvalue(self):
        name = factory.make_name('seq', sep='')
        minvalue = random.randint(1, 50)
        seq = Sequence(name, minvalue=minvalue)
        seq.create()
        val = self.query_seq(seq.name)
        self.assertEqual(minvalue, val)

    def test_sequence_respects_incr(self):
        name = factory.make_name('seq', sep='')
        incr = random.randint(1, 50)
        seq = Sequence(name, incr=incr)
        seq.create()
        val = self.query_seq(seq.name)
        val = self.query_seq(seq.name)
        self.assertEqual(1 + incr, val)

    def test_sequence_respects_maxvalue_and_cycles(self):
        name = factory.make_name('seq', sep='')
        maxvalue = random.randint(10, 50)
        seq = Sequence(name, maxvalue=maxvalue)
        seq.create()
        cursor = connection.cursor()
        query = "ALTER SEQUENCE %s" % seq.name
        cursor.execute(query + " RESTART WITH %s", [maxvalue])
        val = self.query_seq(seq.name)
        val = self.query_seq(seq.name)
        self.assertEqual(1, val)

    def test_drop_sequence(self):
        name = factory.make_name('seq', sep='')
        seq = Sequence(name)
        seq.create()
        seq.drop()
        self.assertRaisesRegexp(
            DatabaseError, "does not exist", self.query_seq,
            seq.name)

    def test_nextval_returns_sequential_values(self):
        name = factory.make_name('seq', sep='')
        seq = Sequence(name)
        seq.create()
        self.assertSequenceEqual(
            range(1, 11), [seq.nextval() for i in range(10)])

# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the "runserver" command module."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.management.commands.runserver import render_error
from maasserver.testing import TestCase


class TestRunServer(TestCase):

    def test_render_error_mentions_oops_id(self):
        fake_oops = {'id': 'EHOVERCRAFTFULL999'}
        self.assertIn(fake_oops['id'], render_error(fake_oops))

    def test_render_error_returns_str(self):
        # wsgi_oops produces oops pages as unicode strings, but django
        # expects raw bytes.  Our own error renderer returns str.
        fake_oops = {'id': 'abc123'}
        self.assertIsInstance(render_error(fake_oops), str)

    def test_render_error_blows_up_if_oops_id_is_not_ascii(self):
        # Oopses mean that things aren't working as they should.  We
        # won't make things worse by including non-ASCII characters in
        # the oops page.
        fake_oops = {'id': '\u2322'}
        self.assertRaises(Exception, render_error, fake_oops)

# Copyright 2005-2011 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from rabbitfixture.server import RabbitServer


# Set setUp() and tearDown().
rabbit = None


def setUp():
    """Package-level fixture hook, recognized by nose."""
    global rabbit
    rabbit = RabbitServer()
    rabbit.setUp()


def tearDown():
    """Package-level fixture hook, recognized by nose."""
    global rabbit
    rabbit.cleanUp()
    rabbit = None

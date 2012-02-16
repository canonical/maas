# Copyright 2005-2011 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "get_rabbit",
    ]

from rabbitfixture.server import RabbitServer

# Set get_rabbit() and tearDown().
rabbit = None


def get_rabbit():
    """Return a running `RabbitServer` fixture."""
    global rabbit
    if rabbit is None:
        rabbit = RabbitServer()
        rabbit.setUp()
    return rabbit


def tearDown():
    """Package-level fixture hook, recognized by nose."""
    global rabbit
    if rabbit is not None:
        rabbit.cleanUp()
        rabbit = None

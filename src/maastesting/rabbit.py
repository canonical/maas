# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for testing with RabbitMQ."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "get_rabbit",
    "start_rabbit",
    "stop_rabbit",
    ]

from rabbitfixture.server import RabbitServer

# See {start,stop,get}_rabbit().
rabbit = None


def start_rabbit():
    """Start a shared :class:`RabbitServer`."""
    global rabbit
    if rabbit is None:
        rabbit = RabbitServer()
        rabbit.setUp()


def stop_rabbit():
    """Stop a shared :class:`RabbitServer`, if any."""
    global rabbit
    if rabbit is not None:
        rabbit.cleanUp()
        rabbit = None


def get_rabbit():
    """Start and return a shared :class:`RabbitServer`."""
    global rabbit
    start_rabbit()
    return rabbit

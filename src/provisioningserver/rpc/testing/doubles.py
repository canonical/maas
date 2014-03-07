# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test doubles for the region's RPC implementation."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DummyConnection",
]

from provisioningserver.rpc.interfaces import IConnection
from zope.interface import implementer


@implementer(IConnection)
class DummyConnection:
    """A dummy connection.

    Implements `IConnection`.
    """

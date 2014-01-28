# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for RPC implementations."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "call_responder",
]


def call_responder(protocol, command, arguments):
    """Call `command` responder in `protocol` with given `arguments`.

    Serialises the arguments and deserialises the response too.
    """
    responder = protocol.locateResponder(command.commandName)
    arguments = command.makeArguments(arguments, protocol)
    d = responder(arguments)
    d.addCallback(command.parseResponse, protocol)
    return d

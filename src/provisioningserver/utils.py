# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "deferred",
    "xmlrpc_export",
    ]

from functools import wraps

from twisted.internet.defer import maybeDeferred
from zope.interface.interface import Method


def deferred(func):
    """Decorates a function to ensure that it always returns a `Deferred`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return maybeDeferred(func, *args, **kwargs)
    return wrapper


def xmlrpc_export(iface):
    """Class decorator to alias methods of a class with an "xmlrpc_" prefix.

    For each method defined in the given interface, the concrete method in the
    decorated class is copied to a new name of "xmlrpc_%(original_name)s". In
    combination with :class:`XMLRPC`, and the rest of the Twisted stack, this
    has the effect of exposing the method via XML-RPC.

    The decorated class must implement `iface`.
    """
    def decorate(cls):
        assert iface.implementedBy(cls), (
            "%s does not implement %s" % (cls.__name__, iface.__name__))
        for name in iface:
            element = iface[name]
            if isinstance(element, Method):
                method = getattr(cls, name)
                setattr(cls, "xmlrpc_%s" % name, method)
        return cls
    return decorate

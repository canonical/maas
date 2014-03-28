# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Registry base class for registry singletons."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Registry",
]

from collections import defaultdict


_registry = defaultdict(dict)


class RegistryType(type):
    """This exists to subvert ``type``'s builtins."""

    def __getitem__(cls, name):
        return _registry[cls][name]

    def __contains__(cls, name):
        return name in _registry[cls]

    def __iter__(cls):
        return _registry[cls].iteritems()

    def get_item(cls, name, default=None):
        return _registry[cls].get(name, default)

    def register_item(cls, name, item):
        _registry[cls][name] = item

    def unregister_item(cls, name):
        _registry[cls].pop(name, None)


class Registry:
    """Base class for singleton registries."""

    __metaclass__ = RegistryType

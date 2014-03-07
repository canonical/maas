# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Registry base class for driver registry singletons."""

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


_registry = {}


class Registry:
    """Base class for singleton registries."""
    registry_name = ''

    @classmethod
    def get_items(cls):
        global _registry
        return _registry.get(cls.registry_name, [])

    @classmethod
    def register_item(cls, item):
        global _registry
        _registry.setdefault(cls.registry_name, [])
        registry = _registry[cls.registry_name]
        if item not in registry:
            registry.append(item)

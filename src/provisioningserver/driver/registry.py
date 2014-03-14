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


class MetaRegistry(type):
    """This exists to subvert "type"s builtins."""
    def __getitem__(self, item):
        return self.get_item(item)

    def __contains__(self, item):
        return item in self.get_items()


class Registry:
    """Base class for singleton registries."""
    __metaclass__ = MetaRegistry
    registry_name = ''

    @classmethod
    def get_items(cls):
        global _registry
        return _registry.get(cls.registry_name, {})

    @classmethod
    def get_item(cls, item):
        global _registry
        return cls.get_items()[item]

    @classmethod
    def register_item(cls, item, name):
        global _registry
        _registry.setdefault(cls.registry_name, {})
        registry = _registry[cls.registry_name]
        registry[name] = item

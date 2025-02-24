# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Registry base class for registry singletons."""

from collections import defaultdict, OrderedDict

# Uses `OrderedDict` so iterating registry occurs in the order of addition.
_registry = defaultdict(OrderedDict)


class RegistryType(type):
    """This exists to subvert ``type``'s builtins."""

    def __getitem__(cls, name):
        return _registry[cls][name]

    def __contains__(cls, name):
        return name in _registry[cls]

    def __iter__(cls):
        return iter(_registry[cls].items())

    def get_item(cls, name, default=None):
        return _registry[cls].get(name, default)

    def register_item(cls, name, item):
        if name in _registry[cls]:
            raise KeyError(f"Key '{name}' is already present in the registry")
        _registry[cls][name] = item

    def unregister_item(cls, name):
        _registry[cls].pop(name, None)


class Registry(metaclass=RegistryType):
    """Base class for singleton registries."""

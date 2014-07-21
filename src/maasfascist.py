# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS-specific import fascist.

This is designed to stop the unwary from importing modules from where
they ought not.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from inspect import getmodule
from sys import (
    _getframe as getframe,
    meta_path,
    )


class FascistFinder:

    # module to import: forbidden from
    rules = {
        "maas": {
            "apiclient",
            "maascli",
            "maastesting",
            "provisioningserver",
        },
        "maasserver": {
            "apiclient",
            "maascli",
            "maastesting",
            "provisioningserver",
        },
        "metadataserver": {
            "apiclient",
            "maascli",
            "maastesting",
            "provisioningserver",
        },
    }

    def find_rule(self, name):
        if name in self.rules:
            return self.rules[name]
        elif "." in name:
            name, _, _ = name.rpartition(".")
            return self.find_rule(name)
        else:
            return None

    def is_forbidden(self, forbidden, name):
        if name in forbidden:
            return True
        elif "." in name:
            name, _, _ = name.rpartition(".")
            return self.is_forbidden(forbidden, name)
        else:
            return False

    def find_module(self, fullname, path=None):
        forbidden = self.find_rule(fullname)
        if forbidden is not None:
            origin_frame = getframe(1)
            origin_module = getmodule(origin_frame)
            if origin_module is not None:
                origin_module_name = origin_module.__name__
                if self.is_forbidden(forbidden, origin_module_name):
                    return FascistLoader(origin_module_name)
        # Good. Out of the door, line on the left, one cross each.
        return None


class FascistLoader:

    def __init__(self, whence):
        super(FascistLoader, self).__init__()
        self.whence = whence

    def load_module(self, name):
        raise ImportError(
            "Naughty, don't import %s from %s" % (name, self.whence))


fascist = FascistFinder()

if fascist not in meta_path:
    meta_path.append(fascist)

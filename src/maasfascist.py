# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS-specific import fascist.

This is designed to stop the unwary from importing modules from where
they ought not.

We do this to help separate concerns. For example, ``provisioningserver`` is
meant to run on cluster controllers, perhaps using code from ``apiclient``,
but it must *not* import from ``maas``, ``maasserver``, or ``metadataserver``
because these are solely the preserve of the region controller, and because
they contain Django applications which need some extra environmental support
in order to run.

See https://docs.python.org/2/library/sys.html#sys.meta_path and
https://docs.python.org/2.7/reference/simple_stmts.html#the-import-statement
for more information on how this module is able to work.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from inspect import (
    getmodule,
    getsourcefile,
)
from sys import (
    _getframe as getframe,
    meta_path,
)


class FascistFinder:
    """Provides the ``find_module`` method.

    ``find_module`` is a Python-specified hook for overriding the normal
    import mechanisms. Put an instance of this class into ``sys.meta_hook``
    and Python will consult it when looking to import a module.

    If ``find_module`` returns an object other than ``None`` it is then used
    to load the module. However, it's also possible to use this to *prevent*
    module loading, which is what this class does in cooperation with
    `FascistLoader`.
    """

    # module to import: forbidden from
    rules = {
        "maas": {
            "apiclient",
            "maascli",
            "maasserver",
            "maastesting",
            "metadataserver",
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
        """Search `rules` for `name`.

        If `name` isn't found but `name` is a dot-separated name, another
        search is attempted with the right-most part of the name removed.
        For example, given `foo.bar.baz` it will search in order::

          foo.bar.baz
          foo.bar
          foo

        If no name matches, it returns `None`.
        """
        if name in self.rules:
            return self.rules[name]
        elif "." in name:
            name, _, _ = name.rpartition(".")
            return self.find_rule(name)
        else:
            return None

    def is_forbidden(self, forbidden, name):
        """Search `forbidden` for `name`.

        If `name` isn't found but `name` is a dot-separated name, another
        search is attempted with the right-most part of the name removed.
        See `find_rule` for details.
        """
        if name in forbidden:
            return True
        elif "." in name:
            name, _, _ = name.rpartition(".")
            return self.is_forbidden(forbidden, name)
        else:
            return False

    def find_module(self, fullname, path=None):
        """Consult `rules` to see if `fullname` can be loaded.

        This ignores `path`.
        """
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

    def install(self):
        """Install this at the front of `meta_path`.

        If it's already installed, it is moved to the front.
        """
        if self in meta_path:
            meta_path.remove(self)
        meta_path.insert(0, self)


class FascistLoader:
    """Prevent import of the specified module.

    With a message explaining what has been prevented and why.
    """

    rules_location = getsourcefile(FascistFinder)
    if rules_location is None:
        rules_location = FascistFinder.__name__

    def __init__(self, whence):
        super(FascistLoader, self).__init__()
        self.whence = whence

    def load_module(self, name):
        """Raises `ImportError` to prevent loading of `name`."""
        raise ImportError(
            "Don't import %r from %r. This is MAAS policy. If you "
            "think this is wrong, amend the rules in %r." % (
                name, self.whence, self.rules_location))


fascist = FascistFinder()
fascist.install()

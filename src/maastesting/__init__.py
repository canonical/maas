# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing infrastructure for MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "bindir",
    "root",
    ]

from os.path import (
    abspath,
    dirname,
    join,
    pardir,
    realpath,
    )
import re
from sys import executable
from warnings import filterwarnings

# The root of the source tree.
root = abspath(join(dirname(realpath(__file__)), pardir, pardir))

# The directory containing the current interpreter.
bindir = abspath(dirname(executable))

# Construct a regular expression that matches all of MAAS's core
# packages, and their subpackages.
packages = {
    "apiclient",
    "maas",
    "maascli",
    "maasserver",
    "maastesting",
    "metadataserver",
    "provisioningserver",
}
packages_expr = r"^(?:%s)\b" % "|".join(
    re.escape(package) for package in packages)

# Enable some warnings that we ought to pay heed to.
filterwarnings('default', category=BytesWarning, module=packages_expr)
filterwarnings('default', category=DeprecationWarning, module=packages_expr)
filterwarnings('default', category=ImportWarning, module=packages_expr)

try:
    import maasfascist
except ImportError:
    pass
else:
    maasfascist  # Silence lint.

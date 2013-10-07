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
    "root",
    ]

from os import listdir
from os.path import (
    abspath,
    dirname,
    join,
    pardir,
    )
import re
from warnings import filterwarnings

# The root of the source tree.
root = abspath(join(dirname(__file__), pardir, pardir))

# Construct a regular expression that matches all of MAAS's core
# packages, and their subpackages.
packages = listdir(join(root, "src"))
packages_expr = r"^(?:%s)\b" % "|".join(
    re.escape(package) for package in packages)

# Enable some warnings that we ought to pay heed to.
filterwarnings('default', category=BytesWarning, module=packages_expr)
filterwarnings('default', category=DeprecationWarning, module=packages_expr)
filterwarnings('default', category=ImportWarning, module=packages_expr)

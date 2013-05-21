# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing infrastructure for MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "root",
    ]

from os.path import (
    abspath,
    dirname,
    join,
    pardir,
    )

# The root of the source tree.
root = abspath(join(dirname(__file__), pardir, pardir))

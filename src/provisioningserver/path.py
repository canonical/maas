# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Compute paths relative to root."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_path',
    ]

from os import getenv
import os.path


def get_path(*path_elements):
    """Return an absolute path based on the `MAAS_ROOT` environment variable.

    Use this to compute paths like `/var/lib/maas/gnupg`, so that development
    environments can redirect them to a playground location.  For example, if
    `MAAS_ROOT` is set to `/tmp/maasroot`, then `get_path()` will return
    `/tmp/maasroot` and `get_path('/var/lib/maas')` returns
    `/tmp/maasroot/var/lib/maas`.  If `MAAS_ROOT` is not set, you just get (a
    normalised version of) the location you passed in; just `get_path()` will
    always return the root directory.

    This call may have minor side effects: it reads environment variables and
    the current working directory.  Side effects during imports are bad, so
    avoid using this in global variables.  Instead of exporting a variable
    that holds your path, export a getter function that returns your path.
    Add caching if it becomes a performance problem.
    """
    maas_root = getenv('MAAS_ROOT', '/')
    # Strip off a leading slash, if any.  If left in, it would override any
    # preceding path elements.  The MAAS_ROOT would be ignored.
    # The dot is there to make the call work even with zero path elements.
    path = os.path.join('.', *path_elements).lstrip('/')
    return os.path.abspath(os.path.join(maas_root, path))

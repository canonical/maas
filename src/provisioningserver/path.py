# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Compute paths relative to root."""

__all__ = [
    'get_path',
    'get_tentative_path',
    ]

import os

from provisioningserver.utils.fs import ensure_dir


def get_root():
    """Return ``MAAS_ROOT`` if set, else "/"."""
    root = os.getenv('MAAS_ROOT')
    if root is None:
        return "/"
    elif len(root) == 0:
        return "/"
    else:
        return root


def get_tentative_path(*path_elements):
    """Return an absolute path based on the `MAAS_ROOT` environment variable.

    Use this to compute paths like ``/var/lib/maas/gnupg``, so that demo and
    development environments can redirect them to a playground location.

    For example:

    * If ``MAAS_ROOT`` is set to ``/tmp/maasroot``, then ``get_path()`` will
      return ``/tmp/maasroot`` and ``get_path('/var/lib/maas')`` will return
      ``/tmp/maasroot/var/lib/maas``.

    * If ``MAAS_ROOT`` is not set, you just get (a normalised version of) the
      location you passed in; just ``get_path()`` will always return the root
      directory.

    This call may have minor side effects: it reads environment variables and
    the current working directory. Side effects during imports are bad, so
    avoid using this in global variables. Instead of exporting a variable that
    holds your path, export a getter function that returns your path. Add
    caching if it becomes a performance problem.
    """
    # Strip off a leading slash from the given path, if any. If it were left
    # in, it would override preceding path elements and MAAS_ROOT would be
    # ignored later on. The dot is there to make the call work even with zero
    # path elements.
    path = os.path.join('.', *path_elements).lstrip('/')
    path = os.path.join(get_root(), path)
    return os.path.abspath(path)


def get_path(*path_elements):
    """Return an absolute path based on the `MAAS_ROOT` environment variable.

    This also ensures that the parent directory of the resultant path exists
    and is a directory.

    See `get_tentative_path` for details.
    """
    path = get_tentative_path(*path_elements)
    # Make sure that the path to the file actually exists.
    ensure_dir(os.path.dirname(path))
    return path

# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Compute paths relative to root."""

from os import getenv, makedirs
from os.path import abspath, dirname, join
from pathlib import Path


def get_path_env(env):
    """Return ``env`` if set, else "/"."""
    path = getenv(env)
    if path is None:
        return "/"
    elif len(path) == 0:
        return "/"
    else:
        return path


def get_tentative_data_path(*path_elements):
    """Return an absolute path based on the `MAAS_ROOT` environment variable.

    Use this to compute paths like ``/var/lib/maas/gnupg``, so that snap, demo,
    and development environments can redirect them to a playground location.

    For example:

    * If ``MAAS_ROOT`` is set to ``/tmp/maasroot``, then
      ``get_tentative_data_path()`` will return ``/tmp/maasroot`` and
      ``get_tentative_data_path('/var/lib/maas')`` will return
      ``/tmp/maasroot/var/lib/maas``.

    * If ``MAAS_ROOT`` is not set, you just get (a normalised version of) the
      location you passed in; just ``get_tentative_data_path()`` will always
      return the root directory.

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
    path = join(".", *path_elements).lstrip("/")
    path = join(get_path_env("MAAS_ROOT"), path)
    return abspath(path)


def get_data_path(*path_elements):
    """Return an absolute path based on the `MAAS_ROOT` environment variable.

    This also ensures that the parent directory of the resultant path exists
    and is a directory.

    See `get_tentative_data_path` for details.
    """
    path = get_tentative_data_path(*path_elements)
    # Make sure that the path to the file actually exists.
    makedirs(dirname(path), exist_ok=True)
    return path


def get_maas_data_path(path: str) -> str:
    """Return a path under the MAAS data path."""
    base_path = Path(getenv("MAAS_DATA", "/var/lib/maas"))
    return str(base_path / path)


def get_maas_lock_path() -> Path:
    """Return a path for lock files."""
    path = Path("/run/lock")
    if name := getenv("SNAP_INSTANCE_NAME"):
        path = path / f"snap.{name}"
    return path


def get_maas_run_path() -> Path:
    """Return a path for run directory."""
    path = Path("/run/maas")
    if name := getenv("SNAP_INSTANCE_NAME"):
        path = Path(f"/run/snap.{name}")
    return path


def get_path(*path_elements):
    """Return an absolute path based on the `MAAS_PATH` environment variable.

    Use this to compute paths like ``/usr/bin/avahi-browse``, so that snap,
    can redirect them to a playground location.

    Unlike ``get_data_path`` the path returned by ``get_path`` does have to
    exists and it will not try to force its existence.

    For example:

    * If ``MAAS_PATH`` is set to ``/snap/maas/current``, then
      ``get_tentative_path()`` will return ``/snap/maas/current`` and
      ``get_tentative_data_path('/usr/bin/avahi-browse')`` will return
      ``/snap/maas/current/usr/bin/avahi-browse``.

    * If ``MAAS_PATH`` is not set, you just get (a normalised version of) the
      location you passed in; just ``get_tentative_path()`` will always
      return the root directory.

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
    path = join(".", *path_elements).lstrip("/")
    path = join(get_path_env("MAAS_PATH"), path)
    return abspath(path)

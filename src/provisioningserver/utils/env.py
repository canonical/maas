# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Environment-related utilities."""

__all__ = [
    'environment_variables',
    ]

from contextlib import contextmanager
import os

from provisioningserver.path import get_path
from provisioningserver.utils.fs import (
    atomic_delete,
    atomic_write,
)


@contextmanager
def environment_variables(variables):
    """Context manager: temporarily set the given environment variables.

    The variables are reset to their original settings afterwards.

    :param variables: A dict mapping environment variables to their temporary
        values.
    """
    prior_environ = os.environ.copy()
    os.environ.update(variables)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(prior_environ)


# Cache the MAAS ID so we don't have to keep reading it from the filesystem.
# This avoids errors when running maas-rack register while regiond is running.
_maas_id = None


def get_maas_id(read_cache=True):
    """Return the system_id for this rack/region controller that is created
    when either the rack or region first starts.
    """
    global _maas_id
    if read_cache and _maas_id is not None:
        return _maas_id

    maas_id_path = get_path('/var/lib/maas/maas_id')
    try:
        with open(maas_id_path, "r", encoding="ascii") as fp:
            contents = fp.read().strip()
    except FileNotFoundError:
        return None
    else:
        _maas_id = _normalise_maas_id(contents)
        return _maas_id


def set_maas_id(system_id):
    """Set the system_id for this rack/region permanently for MAAS."""
    global _maas_id
    maas_id_path = get_path('/var/lib/maas/maas_id')
    maas_id = _normalise_maas_id(system_id)
    if maas_id is None:
        try:
            atomic_delete(maas_id_path)
        except FileNotFoundError:
            pass  # Job done already.
        _maas_id = None
    else:
        atomic_write(maas_id.encode("ascii"), maas_id_path)
        _maas_id = maas_id


def _normalise_maas_id(system_id):
    if system_id is None:
        return None
    else:
        system_id = system_id.strip()
        return None if system_id == "" else system_id

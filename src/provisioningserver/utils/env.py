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


def get_maas_id():
    """Return the system_id for this rack/region controller that is created
    when either the rack or region first starts.
    """
    maas_id_path = get_path('/var/lib/maas/maas_id')
    try:
        with open(maas_id_path, "r", encoding="ascii") as fp:
            contents = fp.read().strip()
    except FileNotFoundError:
        return None
    else:
        return _normalise_maas_id(contents)


def set_maas_id(system_id):
    """Set the system_id for this rack/region permanently for MAAS."""
    maas_id_path = get_path('/var/lib/maas/maas_id')
    if _normalise_maas_id(system_id) is None:
        try:
            atomic_delete(maas_id_path)
        except FileNotFoundError:
            pass  # Job done already.
    else:
        atomic_write(system_id.encode("ascii"), maas_id_path)


def _normalise_maas_id(system_id):
    if system_id is None:
        return None
    else:
        system_id = system_id.strip()
        return None if system_id == "" else system_id

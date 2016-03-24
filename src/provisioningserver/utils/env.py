# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Environment-related utilities."""

__all__ = [
    'environment_variables',
    ]

from contextlib import contextmanager
import os

from provisioningserver.path import get_path
from provisioningserver.utils.fs import atomic_write


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
    if os.path.exists(maas_id_path):
        with open(maas_id_path, "r", encoding="ascii") as fp:
            return fp.read().strip()
    else:
        return None


def set_maas_id(system_id):
    """Set the system_id for this rack/region permanently for MAAS."""
    maas_id_path = get_path('/var/lib/maas/maas_id')
    atomic_write(system_id.encode("ascii"), maas_id_path)

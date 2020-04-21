# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = ["get_deprecations", "log_deprecations"]

from copy import deepcopy

from provisioningserver.logger import LegacyLogger
from provisioningserver.utils import snappy

DEPRECATION_URL = "https://maas.io/deprecations/{id}"

# all known deprecation notices
DEPRECATIONS = {
    "MD1": {
        "since": "2.8",
        "link-text": "How to migrate the database out of the snap",
        "description": (
            "The setup for this MAAS is deprecated and not suitable for production "
            "environments, as the database is running inside the snap."
        ),
    }
}


def get_deprecations():
    """Return a list of currently active deprecation notices."""
    deprecations = []

    def add_deprecation(id):
        deprecation = deepcopy(DEPRECATIONS[id])
        deprecation["id"] = id
        deprecation["url"] = DEPRECATION_URL.format(id=id)
        deprecations.append(deprecation)

    if snappy.running_in_snap() and snappy.get_snap_mode() == "all":
        add_deprecation("MD1")

    return deprecations


def log_deprecations(logger=None):
    """Log active deprecations."""
    if logger is None:
        logger = LegacyLogger()

    for d in get_deprecations():
        logger.msg("Deprecation {id} ({url}): {description}".format(**d))

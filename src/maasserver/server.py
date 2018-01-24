# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Entrypoint for the maas regiond service."""

from provisioningserver.server import runService


def run():
    """Run the maas-regiond service."""
    runService('maas-regiond')

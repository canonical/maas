# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Entrypoint for the maas rackd service."""

# Install the asyncio reactor with uvloop. This must be done before any other
# twisted code is imported.
import asyncio
import sys

from twisted.internet import asyncioreactor
from twisted.python import usage
from twisted.scripts._twistd_unix import ServerOptions, UnixApplicationRunner

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass
asyncioreactor.install()


# Load the available MAAS plugins.
twistd_plugins = []
try:
    from provisioningserver.plugin import ProvisioningServiceMaker
except ImportError:
    pass
else:
    # Rackd service that twisted will spawn.
    twistd_plugins.append(
        ProvisioningServiceMaker(
            "maas-rackd", "The MAAS Rack Controller daemon."
        )
    )

try:
    from maasserver.plugin import (
        RegionAllInOneServiceMaker,
        RegionMasterServiceMaker,
        RegionWorkerServiceMaker,
    )
except ImportError:
    pass
else:
    # Regiond services that twisted could spawn.
    twistd_plugins.append(
        RegionMasterServiceMaker(
            "maas-regiond-master", "The MAAS Region Controller master process."
        )
    )
    twistd_plugins.append(
        RegionWorkerServiceMaker(
            "maas-regiond-worker", "The MAAS Region Controller worker process."
        )
    )
    twistd_plugins.append(
        RegionAllInOneServiceMaker(
            "maas-regiond-all",
            "The MAAS Region Controller all-in-one process.",
        )
    )


class Options(ServerOptions):
    """Override the plugins path for the server options."""

    @staticmethod
    def _getPlugins(interface):
        return twistd_plugins


def runService(service):
    """Run the `service`."""
    config = Options()
    args = [
        "--logger=provisioningserver.logger.EventLogger",
        "--nodaemon",
        "--pidfile=",
    ]
    args += sys.argv[1:]
    args += [service]
    try:
        config.parseOptions(args)
    except usage.error as exc:
        print(config)
        print(f"{sys.argv[0]}: {exc}")
    else:
        UnixApplicationRunner(config).run()


def run():
    """Run the maas-rackd service."""
    runService("maas-rackd")

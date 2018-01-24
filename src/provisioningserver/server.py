# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Entrypoint for the maas rackd service."""

# Install the asyncio reactor with uvloop. This must be done before any other
# twisted code is imported.
import asyncio
import sys

from twisted.internet import asyncioreactor


try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass
asyncioreactor.install()


from twisted.python import usage
from twisted.scripts._twistd_unix import ServerOptions, UnixApplicationRunner


def runService(service):
    """Run the `service`."""
    config = ServerOptions()
    args = [
        '--logger=provisioningserver.logger.EventLogger',
        '--nodaemon', '--pidfile=',
    ]
    args += sys.argv[1:]
    args += [service]
    try:
        usage.Options.parseOptions(config, args)
    except usage.error as exc:
        print(config)
        print("%s: %s" % (sys.argv[0], exc))
    else:
        UnixApplicationRunner(config).run()


def run():
    """Run the maas-rackd service."""
    runService('maas-rackd')

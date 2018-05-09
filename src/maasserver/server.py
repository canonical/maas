# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Entrypoint for the maas regiond service."""

import argparse
import os
import signal
import sys

# Set the default so on installed system running regiond directly just works.
os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE", "maasserver.djangosettings.settings")


def installUvloop():
    """Install uvloop to asyncio to use."""
    # XXX blake_r: LP: #1768575 - This is only done for the regiond, the rackd
    # uses the standard asyncio reactor. Once rackd removes the need for
    # authbind then it can be moved back into the region and this can be
    # removed.
    import asyncio
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass


def runMasterServices():
    """Run the maas-regiond master services."""
    installUvloop()
    from provisioningserver.server import runService
    runService("maas-regiond-master")


def runAllInOneServices():
    """Run the maas-regiond all-in-one services."""
    installUvloop()
    from provisioningserver.server import runService
    runService("maas-regiond-all")


def runWorkerServices():
    """Run the worker service."""
    installUvloop()
    from provisioningserver.server import runService
    runService("maas-regiond-worker")


def parse():
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(
        description='MAAS region controller process')
    parser.add_argument(
        '-d', '--debug', action='store_true', help=(
            "Run in debug mode. Doesn't fork and keeps all services "
            "in the spawned process."))
    parser.add_argument(
        '-w', '--workers', metavar='N', type=int, help=(
            "Number of worker process to spawn."))
    return parser.parse_args()


def run():
    """Run the maas-regiond master service.

    Spawns children workers up to the number of CPU's minimum is 4 workers.
    """
    args = parse()

    # Remove all the command line arguments, so they don't interfere with
    # the twistd argument parser.
    sys.argv = sys.argv[:1]

    # Workers are spawned with environment so it knows that it would only
    # be a worker.
    if os.environ.get('MAAS_REGIOND_PROCESS_MODE') == 'worker':
        # Ignore interrupt on the workers. The master will kill them directly.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        runWorkerServices()
        return

    # Circular imports.
    from maasserver.workers import set_max_workers_count

    # Debug mode, run the all-in-one mode.
    if args.debug:
        set_max_workers_count(1)
        runAllInOneServices()
        return

    # Calculate the number of workers.
    worker_count = args.workers
    if not worker_count:
        from maasserver.config import RegionConfiguration
        try:
            with RegionConfiguration.open() as config:
                worker_count = config.num_workers
        except:
            worker_count = 4
    if worker_count <= 0:
        raise ValueError('Number of workers must be greater than zero.')

    # Set the maximum number of workers.
    set_max_workers_count(worker_count)

    # Start the master services, which will spawn the required workers.
    runMasterServices()

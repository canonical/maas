import asyncio
import os
import sys

from twisted.internet import asyncioreactor, error, reactor
import uvloop

from maasserver import execute_from_command_line
from maasserver.utils import orm, threads
from maastesting.noseplug import main as test_main
from maastesting.parallel import main as test_parallel_main
from provisioningserver import logger


def init_asyncio_reactor():
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    try:
        asyncioreactor.install()
    except error.ReactorAlreadyInstalledError:
        pass


def inject_test_options(options):
    # set default verbosity
    options = options.copy()
    options.append(f"--verbosity={1 if sys.stdout.isatty() else 2}")
    sys.argv[1:1] = options


def update_environ(env=None):
    os.environ.update(
        {
            "MAAS_ROOT": os.path.join(os.getcwd(), ".run"),
            "MAAS_DATA": os.path.join(os.getcwd(), ".run/maas"),
            "DJANGO_SETTINGS_MODULE": "maasserver.djangosettings.development",
        }
    )
    if env:
        os.environ.update(env)


def run_region():
    """Entry point for region test runner."""
    options = [
        "--with-crochet",
        "--with-resources",
        "--with-scenarios",
        "--with-select",
        "--select-dir=src/maasserver",
        "--select-dir=src/metadataserver",
        "--cover-package=maas,maasserver,metadataserver",
        "--cover-branches",
        # Reduce the logging level to INFO here as
        # DebuggingLoggerMiddleware logs the content of all the
        # requests at DEBUG level: we don't want this in the
        # tests as it's too verbose.
        "--logging-level=INFO",
        "--logging-clear-handlers",
        # Do not run tests tagged "legacy".
        "-a",
        "!legacy",
    ]
    inject_test_options(options)
    update_environ()
    init_asyncio_reactor()

    logger.configure(mode=logger.LoggingMode.COMMAND)
    # Limit concurrency in all thread-pools to ONE.
    threads.install_default_pool(maxthreads=1)
    threads.install_database_unpool(maxthreads=1)

    # Disable all database connections in the reactor.
    assert not reactor.running, "The reactor has been started too early."
    reactor.callFromThread(orm.disable_all_database_connections)

    # Configure Django
    import django

    django.setup()
    test_main()


def run_region_legacy():
    """Entry point for legacy region test runner."""
    options = [
        "test",
        "--noinput",
        "--with-crochet",
        "--with-scenarios",
        "--with-select",
        "--select-dir=src/maasserver",
        "--select-dir=src/metadataserver",
        "--cover-package=maas,maasserver,metadataserver",
        "--cover-branches",
        # Reduce the logging level to INFO here as DebuggingLoggerMiddleware
        # logs the content of all the requests at DEBUG level: we don't want
        # this in the tests as it's too verbose.
        "--logging-level=INFO",
        "--logging-clear-handlers",
        # Run only tests tagged "legacy".
        "-a",
        "legacy",
    ]
    inject_test_options(options)
    update_environ(env={"MAAS_PREVENT_MIGRATIONS": "1"})
    init_asyncio_reactor()
    execute_from_command_line()


def run_rack():
    """Entry point for rack test runner."""
    options = [
        "--with-crochet",
        "--crochet-no-setup",
        "--with-resources",
        "--with-scenarios",
        "--with-select",
        "--select-dir=src/provisioningserver",
        "--cover-package=provisioningserver",
        "--cover-branches",
    ]
    inject_test_options(options)
    update_environ()
    init_asyncio_reactor()
    test_main()


def run_parallel():
    """Entry point for parallel test runner."""
    init_asyncio_reactor()
    update_environ()
    test_parallel_main()

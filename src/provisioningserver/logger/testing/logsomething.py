# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""A script that configures and then logs via:

- The Twisted modern logging system.

- The Twisted modern logging systems.

- The standard library's `logging` system.

- The standard library's `warnings` system.

- Standard output.

- Standard error.

"""

import argparse
import logging
import sys
import warnings

import twisted.logger
import twisted.python.log

import provisioningserver.logger


def main():
    modes = provisioningserver.logger.LoggingMode

    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--verbosity", type=int, required=True)
    # Resets the verbosity at runtime (after initially setting it).
    parser.add_argument("--set-verbosity", type=int, required=False)
    parser.add_argument(
        "--mode",
        type=modes.__getitem__,
        help=" or ".join(mode.name for mode in modes),
    )
    options = parser.parse_args()

    # Configure logging. This is the main entry-point.
    provisioningserver.logger.configure(
        verbosity=options.verbosity, mode=options.mode
    )

    if options.set_verbosity is not None:
        provisioningserver.logger.set_verbosity(options.set_verbosity)

    # Simulate what `twistd` does when passed `--logger=...` in Twisted 16.0.
    # In 16.4 a similar thing happens, but globalLogBeginner.beginLoggingTo()
    # is called without going via `twisted.python.log`.
    if options.mode == modes.TWISTD:
        emitter = provisioningserver.logger.EventLogger()
        twisted.python.log.startLoggingWithObserver(emitter)

    # Twisted, new.
    twisted.logger.Logger(options.name).debug("From `twisted.logger`.")
    twisted.logger.Logger(options.name).info("From `twisted.logger`.")
    twisted.logger.Logger(options.name).warn("From `twisted.logger`.")
    twisted.logger.Logger(options.name).error("From `twisted.logger`.")

    # Twisted, legacy.
    twisted.python.log.msg("From `twisted.python.log`.", system=options.name)
    # Twisted, legacy `logfile`. This has its own namespace.
    twisted.python.log.logfile.write("From `twisted.python.log.logfile`.\n")

    # Standard library.
    logging.getLogger(options.name).debug("From `logging`.")
    logging.getLogger(options.name).info("From `logging`.")
    logging.getLogger(options.name).warning("From `logging`.")
    logging.getLogger(options.name).error("From `logging`.")

    # Standard library, "maas" logger.
    maaslog = provisioningserver.logger.get_maas_logger(options.name)
    maaslog.debug("From `get_maas_logger`.")
    maaslog.info("From `get_maas_logger`.")
    maaslog.warning("From `get_maas_logger`.")
    maaslog.error("From `get_maas_logger`.")

    # Standard IO.
    print("Printing to stdout.", file=sys.stdout, flush=True)
    print("Printing to stderr.", file=sys.stderr, flush=True)

    # Warnings.
    warnings.formatwarning = lambda message, *_, **__: str(message)
    warnings.warn("This is a warning!")  # noqa: B028

    # Make sure everything is flushed.
    sys.stdout.flush()
    sys.stderr.flush()


if __name__ == "__main__":
    main()

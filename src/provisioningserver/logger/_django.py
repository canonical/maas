# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django-specific logging stuff."""

import warnings

from provisioningserver.logger._common import (
    is_dev_environment,
    LoggingMode,
    warn_unless,
)


def configure_django_logging(verbosity: int, mode: LoggingMode):
    """Do basic logging configuration for Django, if possible.

    Then destroy Django's ability to mess with logging configuration. We have
    to do this by monkey-patching because changing Django's settings at
    run-time is not supported. If Django is not installed this is a no-op.

    :param verbosity: See `get_logging_level`.
    :param mode: The mode in which to configure logging. See `LoggingMode`.
    """
    try:
        from django.utils import log
    except ImportError:
        # Django not installed; nothing to be done.
        return

    # Django's default logging configuration is not great. For example it
    # wants to email request errors and security issues to the site admins,
    # but fails silently. Throw it all away.
    warn_unless(
        hasattr(log, "DEFAULT_LOGGING"),
        "No DEFAULT_LOGGING attribute found in Django; please investigate!",
    )
    log.DEFAULT_LOGGING = {"version": 1, "disable_existing_loggers": False}

    # Prevent Django from meddling with `warnings`. There's no configuration
    # option for this so we have to get invasive. We also skip running-in
    # Django's default log configuration even though we threw it away already.
    def configure_logging(logging_config, logging_settings):
        """Reduced variant of Django's configure_logging."""
        if logging_config is not None:
            logging_config_func = log.import_string(logging_config)
            logging_config_func(logging_settings)

    warn_unless(
        hasattr(log, "configure_logging"),
        "No configure_logging function found in Django; please investigate!",
    )
    log.configure_logging = configure_logging

    # Outside of the development environment ensure that deprecation warnings
    # from Django are silenced. End users are _not_ interested in deprecation
    # warnings from Django. Developers are, however.
    if not is_dev_environment():
        from django.utils.deprecation import RemovedInNextVersionWarning

        warnings.simplefilter("ignore", RemovedInNextVersionWarning)

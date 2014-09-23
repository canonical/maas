# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioning server tasks that are run in Celery workers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'rndc_command',
    'setup_rndc_configuration',
    'write_dns_config',
    'write_dns_zone_config',
    'write_full_dns_config',
    ]

from functools import wraps
from subprocess import CalledProcessError

from celery.app import app_or_default
from celery.task import task
from provisioningserver.dns.config import (
    DNSConfig,
    execute_rndc_command,
    set_up_options_conf,
    setup_rndc,
    )
from provisioningserver.logger import get_maas_logger
from provisioningserver.logger.utils import log_call


celery_config = app_or_default().conf

maaslog = get_maas_logger("tasks")


# The tasks catch bare exceptions in an attempt to circumvent Celery's
# bizarre exception handling which prints a stack trace but not the
# error message contained in the exception itself!  The message is
# printed and then the exception re-raised so that it marks the task as
# failed - in doing so it logs the stack trace, which is why the code
# does not do a simple maaslog.exception(exc).
def log_exception_text(func):
    """Wrap a function and log any exception text raised."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            maaslog.error("%s: %s", func.__name__, unicode(e))
            raise
    return wrapper


# =====================================================================
# DNS-related tasks
# =====================================================================

# How many times should a rndc task be retried?
RNDC_COMMAND_MAX_RETRY = 10

# How long to wait between rndc tasks retries (in seconds)?
RNDC_COMMAND_RETRY_DELAY = 2


@task(max_retries=RNDC_COMMAND_MAX_RETRY, queue=celery_config.WORKER_QUEUE_DNS)
@log_call()
@log_exception_text
def rndc_command(arguments, retry=False, callback=None):
    """Use rndc to execute a command.
    :param arguments: Argument list passed down to the rndc command.
    :type arguments : list
    :param retry: Should this task be retried in case of failure?
    :type retry: bool
    :param callback: Callback subtask.
    :type callback: callable
    """
    try:
        execute_rndc_command(arguments)
    except CalledProcessError as exc:
        if retry:
            return rndc_command.retry(
                exc=exc, countdown=RNDC_COMMAND_RETRY_DELAY)
        else:
            maaslog.error("rndc_command failed: %s", unicode(exc))
            raise
    if callback is not None:
        callback.delay()


@task(queue=celery_config.WORKER_QUEUE_DNS)
@log_call()
@log_exception_text
def write_full_dns_config(zones=None, callback=None, **kwargs):
    """Write out the DNS configuration files: the main configuration
    file and the zone files.
    :param zones: List of zones to write.
    :type zones: list of :class:`DNSZoneData`
    :param callback: Callback subtask.
    :type callback: callable
    :param **kwargs: Keyword args passed to DNSConfig.write_config()
    """
    if zones is not None:
        for zone in zones:
            zone.write_config()
    # Write main config file.
    dns_config = DNSConfig(zones=zones)
    dns_config.write_config(**kwargs)
    # Write the included options file.
    set_up_options_conf(**kwargs)
    if callback is not None:
        callback.delay()


@task(queue=celery_config.WORKER_QUEUE_DNS)
@log_call()
@log_exception_text
def write_dns_config(zones=(), callback=None, **kwargs):
    """Write out the DNS configuration file.

    :param zones: List of zones to include as part of the main
        config.
    :type zones: list of :class:`DNSZoneData`
    :param callback: Callback subtask.
    :type callback: callable
    :param **kwargs: Keyword args passed to DNSConfig.write_config()
    """
    dns_config = DNSConfig(zones=zones)
    dns_config.write_config(**kwargs)
    if callback is not None:
        callback.delay()


@task(queue=celery_config.WORKER_QUEUE_DNS)
@log_call()
@log_exception_text
def write_dns_zone_config(zones, callback=None, **kwargs):
    """Write out DNS zones.

    :param zone: The zone data to write the configuration for.
    :type zone: :class:`DNSZoneData`
    :param callback: Callback subtask.
    :type callback: callable
    :param **kwargs: Keyword args passed to DNSZoneConfig.write_config()
    """
    for zone in zones:
        zone.write_config()
    if callback is not None:
        callback.delay()


@task(queue=celery_config.WORKER_QUEUE_DNS)
@log_call()
@log_exception_text
def setup_rndc_configuration(callback=None):
    """Write out the two rndc configuration files (rndc.conf and
    named.conf.rndc).

    :param callback: Callback subtask.
    :type callback: callable
    """
    setup_rndc()
    if callback is not None:
        callback.delay()

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
    'refresh_secrets',
    'report_boot_images',
    'rndc_command',
    'setup_rndc_configuration',
    'write_dns_config',
    'write_dns_zone_config',
    'write_full_dns_config',
    ]

from functools import wraps
import logging
from subprocess import CalledProcessError

from celery.app import app_or_default
from celery.task import task
from provisioningserver import (
    boot_images,
    tags,
    )
from provisioningserver.auth import (
    record_api_credentials,
    record_nodegroup_uuid,
    )
from provisioningserver.dns.config import (
    DNSConfig,
    execute_rndc_command,
    set_up_options_conf,
    setup_rndc,
    )
from provisioningserver.logger import get_maas_logger
from provisioningserver.logger.utils import log_call

# For each item passed to refresh_secrets, a refresh function to give it to.
refresh_functions = {
    'api_credentials': record_api_credentials,
    'nodegroup_uuid': record_nodegroup_uuid,
}


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


@task
@log_call()
@log_exception_text
def refresh_secrets(**kwargs):
    """Update the worker's knowledge of various secrets it needs.

    The worker shares some secrets with the MAAS server, such as its
    omapi key for talking to the DHCP server, and its MAAS API credentials.
    When the server sends tasks to the worker, the tasks will include these
    secrets as needed.  But not everything the worker does is initiated by
    a server request, so it needs copies of these secrets at hand.

    We don't store these secrets in the worker, but we hold copies in
    memory.  The worker won't perform jobs that require secrets it does
    not have yet, waiting instead for the next chance to catch up.

    To make sure that the worker does not have to wait too long, the server
    can send periodic `refresh_secrets` messages with the required
    information.

    Tasks can also call `refresh_secrets` to record information they receive
    from the server.

    All refreshed items are passed as keyword arguments, to avoid confusion
    and allow for easy reordering.  All refreshed items are optional.  An
    item that is not passed will not be refreshed, so it's entirely valid to
    call this for just a single item.  However `None` is a value like any
    other, so passing `foo=None` will cause item `foo` to be refreshed with
    value `None`.

    To help catch simple programming mistakes, passing an unknown argument
    will result in an assertion failure.

    :param api_credentials: A colon separated string containing this
        worker's credentials for accessing the MAAS API: consumer key,
        resource token, resource secret.
    :param nodegroup_uuid: The uuid of the node group that this worker
        manages.
    """
    for key, value in kwargs.items():
        assert key in refresh_functions, "Unknown refresh item: %s" % key
        refresh_functions[key](value)


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


# =====================================================================
# Boot images-related tasks
# =====================================================================


@task
@log_call(level=logging.DEBUG)
@log_exception_text
def report_boot_images():
    """For master worker only: report available netboot images."""
    boot_images.report_to_server()


# How many times should a update node tags task be retried?
UPDATE_NODE_TAGS_MAX_RETRY = 10

# How long to wait between update node tags task retries (in seconds)?
UPDATE_NODE_TAGS_RETRY_DELAY = 2


# =====================================================================
# Tags-related tasks
# =====================================================================


@task(max_retries=UPDATE_NODE_TAGS_MAX_RETRY)
@log_call()
@log_exception_text
def update_node_tags(tag_name, tag_definition, tag_nsmap, retry=True):
    """Update the nodes for a new/changed tag definition.

    :param tag_name: Name of the tag to update nodes for
    :param tag_definition: Tag definition
    :param retry: Whether to retry on failure
    """
    try:
        tags.process_node_tags(tag_name, tag_definition, tag_nsmap)
    except tags.MissingCredentials, exc:
        if retry:
            return update_node_tags.retry(
                exc=exc, countdown=UPDATE_NODE_TAGS_RETRY_DELAY)
        else:
            raise

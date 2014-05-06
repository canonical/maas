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
    'power_off',
    'power_on',
    'refresh_secrets',
    'report_boot_images',
    'rndc_command',
    'setup_rndc_configuration',
    'restart_dhcp_server',
    'stop_dhcp_server',
    'write_dhcp_config',
    'write_dns_config',
    'write_dns_zone_config',
    'write_full_dns_config',
    ]

from functools import wraps
from logging import getLogger
from subprocess import CalledProcessError

from celery.app import app_or_default
from celery.task import task
from provisioningserver import (
    boot_images,
    tags,
    )
from provisioningserver.auth import (
    MAAS_USER_GPGHOME,
    record_api_credentials,
    record_nodegroup_uuid,
    )
from provisioningserver.custom_hardware.seamicro import (
    probe_seamicro15k_and_enlist,
    )
from provisioningserver.custom_hardware.ucsm import probe_and_enlist_ucsm
from provisioningserver.dhcp import (
    config,
    detect,
    )
from provisioningserver.dhcp.leases import upload_leases
from provisioningserver.dns.config import (
    DNSConfig,
    execute_rndc_command,
    set_up_options_conf,
    setup_rndc,
    )
from provisioningserver.import_images import boot_resources
from provisioningserver.omshell import Omshell
from provisioningserver.power.poweraction import (
    PowerAction,
    PowerActionFail,
    )
from provisioningserver.utils import (
    call_and_check,
    find_ip_via_arp,
    sudo_write_file,
    )
from provisioningserver.utils.env import environment_variables

# For each item passed to refresh_secrets, a refresh function to give it to.
refresh_functions = {
    'api_credentials': record_api_credentials,
    'nodegroup_uuid': record_nodegroup_uuid,
}


celery_config = app_or_default().conf

logger = getLogger(__name__)


# The tasks catch bare exceptions in an attempt to circumvent Celery's
# bizarre exception handling which prints a stack trace but not the
# error message contained in the exception itself!  The message is
# printed and then the exception re-raised so that it marks the task as
# failed - in doing so it logs the stack trace, which is why the code
# does not do a simple logger.exception(exc).
def log_exception_text(func):
    """Wrap a function and log any exception text raised."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            logger.error("%s: %s", func.__name__, unicode(e))
            raise
    return wrapper


@task
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
# Power-related tasks
# =====================================================================


def issue_power_action(power_type, power_change, **kwargs):
    """Issue a power action to a node.

    :param power_type: The node's power type.  Must have a corresponding
        power template.
    :param power_change: The change to request: 'on' or 'off'.
    :param **kwargs: Keyword arguments are passed on to :class:`PowerAction`.
    """
    assert power_change in ('on', 'off'), (
        "Unknown power change keyword: %s" % power_change)
    kwargs['power_change'] = power_change
    if 'mac_address' in kwargs:
        kwargs['ip_address'] = find_ip_via_arp(kwargs['mac_address'])
    kwargs.setdefault('ip_address', None)
    try:
        pa = PowerAction(power_type)
        pa.execute(**kwargs)
    except PowerActionFail:
        # TODO: signal to webapp that it failed

        # Re-raise, so the job is marked as failed.  Only currently
        # useful for tests.
        raise

    # TODO: signal to webapp that it worked.


@task
@log_exception_text
def power_on(power_type, **kwargs):
    """Turn a node on."""
    issue_power_action(power_type, 'on', **kwargs)


@task
@log_exception_text
def power_off(power_type, **kwargs):
    """Turn a node off."""
    issue_power_action(power_type, 'off', **kwargs)


# =====================================================================
# DNS-related tasks
# =====================================================================

# How many times should a rndc task be retried?
RNDC_COMMAND_MAX_RETRY = 10

# How long to wait between rndc tasks retries (in seconds)?
RNDC_COMMAND_RETRY_DELAY = 2


@task(max_retries=RNDC_COMMAND_MAX_RETRY, queue=celery_config.WORKER_QUEUE_DNS)
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
            logger.error("rndc_command failed: %s", unicode(exc))
            raise
    if callback is not None:
        callback.delay()


@task(queue=celery_config.WORKER_QUEUE_DNS)
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
# DHCP-related tasks
# =====================================================================


@task
@log_exception_text
def upload_dhcp_leases():
    """Upload DHCP leases.

    Uploads leases to the MAAS API, using cached credentials -- the task
    originates with celerybeat, not with a server request.
    """
    upload_leases()


@task
@log_exception_text
def add_new_dhcp_host_map(mappings, server_address, shared_key):
    """Add address mappings to the DHCP server.

    Do not invoke this when DHCP is set to be managed manually.

    :param mappings: A dict of new IP addresses, and the MAC addresses they
        translate to.
    :param server_address: IP or hostname for the DHCP server
    :param shared_key: The HMAC-MD5 key that the DHCP server uses for access
        control.
    """
    omshell = Omshell(server_address, shared_key)
    try:
        for ip_address, mac_address in mappings.items():
            omshell.create(ip_address, mac_address)
    except CalledProcessError as e:
        # TODO signal to webapp that the job failed.

        # Re-raise, so the job is marked as failed.  Only currently
        # useful for tests.
        logger.error("add_new_dhcp_host_map failed: %s", unicode(e))
        raise


@task
@log_exception_text
def remove_dhcp_host_map(ip_address, server_address, omapi_key):
    """Remove an IP to MAC mapping in the DHCP server.

    Do not invoke this when DHCP is set to be managed manually.

    :param ip_address: Dotted quad string
    :param server_address: IP or hostname for the DHCP server
    :param omapi_key: The HMAC-MD5 key that the DHCP server uses for access
        control.
    """
    omshell = Omshell(server_address, omapi_key)
    try:
        omshell.remove(ip_address)
    except CalledProcessError as e:
        # TODO signal to webapp that the job failed.

        # Re-raise, so the job is marked as failed.  Only currently
        # useful for tests.
        logger.error("remove_dhcp_host_map failed: %s", unicode(e))
        raise


@task
@log_exception_text
def write_dhcp_config(callback=None, **kwargs):
    """Write out the DHCP configuration file and restart the DHCP server.

    :param dhcp_interfaces: Space-separated list of interfaces that the
        DHCP server should listen on.
    :param **kwargs: Keyword args passed to dhcp.config.get_config()
    """
    sudo_write_file(
        celery_config.DHCP_CONFIG_FILE, config.get_config(**kwargs))
    sudo_write_file(
        celery_config.DHCP_INTERFACES_FILE, kwargs.get('dhcp_interfaces', ''))
    if callback is not None:
        callback.delay()


@task
@log_exception_text
def restart_dhcp_server():
    """Restart the DHCP server."""
    call_and_check(['sudo', '-n', 'service', 'maas-dhcp-server', 'restart'])


@task
@log_exception_text
def stop_dhcp_server():
    """Stop a DHCP server."""
    call_and_check(['sudo', '-n', 'service', 'maas-dhcp-server', 'stop'])


@task
@log_exception_text
def periodic_probe_dhcp():
    """Probe for foreign DHCP servers."""
    detect.periodic_probe_task()


# =====================================================================
# Boot images-related tasks
# =====================================================================


@task
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


# =====================================================================
# Image importing-related tasks
# =====================================================================

@task
@log_exception_text
def import_boot_images(http_proxy=None, callback=None):
    config = boot_resources.read_config()
    variables = {
        'GNUPGHOME': MAAS_USER_GPGHOME,
        }
    if http_proxy is not None:
        variables['http_proxy'] = http_proxy
        variables['https_proxy'] = http_proxy
    with environment_variables(variables):
        boot_resources.import_images(config)
    if callback is not None:
        callback.delay()


# =====================================================================
# Custom hardware tasks
# =====================================================================

@task
@log_exception_text
def add_seamicro15k(mac, username, password, power_control=None):
    """ See `maasserver.api.NodeGroupsHandler.add_seamicro15k`. """
    ip = find_ip_via_arp(mac)
    if ip is not None:
        probe_seamicro15k_and_enlist(
            ip, username, password,
            power_control=power_control)
    else:
        logger.warning("Couldn't find IP address for MAC %s" % mac)


@task
@log_exception_text
def enlist_nodes_from_ucsm(url, username, password):
    """ See `maasserver.api.NodeGroupsHandler.enlist_nodes_from_ucsm`. """
    probe_and_enlist_ucsm(url, username, password)

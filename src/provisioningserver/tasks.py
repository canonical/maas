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

from base64 import b64decode
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
    MAAS_USER_GPGHOME,
    record_api_credentials,
    record_nodegroup_uuid,
    )
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
from provisioningserver.drivers.hardware.mscm import probe_and_enlist_mscm
from provisioningserver.drivers.hardware.seamicro import (
    probe_seamicro15k_and_enlist,
    )
from provisioningserver.drivers.hardware.ucsm import probe_and_enlist_ucsm
from provisioningserver.drivers.hardware.virsh import probe_virsh_and_enlist
from provisioningserver.import_images import boot_resources
from provisioningserver.logger import get_maas_logger
from provisioningserver.omshell import Omshell
from provisioningserver.power.poweraction import PowerAction
from provisioningserver.utils import (
    call_and_check,
    ExternalProcessError,
    sudo_write_file,
    warn_deprecated,
    )
from provisioningserver.utils.env import environment_variables
from provisioningserver.utils.network import find_ip_via_arp

# For each item passed to refresh_secrets, a refresh function to give it to.
refresh_functions = {
    'api_credentials': record_api_credentials,
    'nodegroup_uuid': record_nodegroup_uuid,
}


celery_config = app_or_default().conf

maaslog = get_maas_logger("tasks")


def log_task_events(level=logging.INFO):
    """Log to the maaslog that something happened with a task.

    :param event: The event that we want to log.
    :param task_name: The name of the task.
    :**kwargs: A dict of args passed to the task.
    """
    def _decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            arg_string = "%s %s" % (args, kwargs)
            maaslog.log(
                level, "Starting task '%s' with args: %s" %
                (func.__name__, arg_string))
            func(*args, **kwargs)
            maaslog.log(
                level, "Finished task '%s' with args: %s" %
                (func.__name__, arg_string))
        return wrapper
    return _decorator


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
@log_task_events()
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


@task
@log_task_events()
@log_exception_text
def power_on(power_type, **kwargs):
    """Turn a node on.

    :deprecated: Use the RPC command
        :py:class:`~provisioningserver.rpc.cluster.PowerOn` instead.
    """
    warn_deprecated("use the PowerOn RPC command instead.")
    pa = PowerAction(power_type)
    pa.execute(power_change='on', **kwargs)


@task
@log_task_events()
@log_exception_text
def power_off(power_type, **kwargs):
    """Turn a node off.

    :deprecated: Use the RPC command
        :py:class:`~provisioningserver.rpc.cluster.PowerOff` instead.
    """
    warn_deprecated("use the PowerOff RPC command instead.")
    pa = PowerAction(power_type)
    pa.execute(power_change='off', **kwargs)


# =====================================================================
# DNS-related tasks
# =====================================================================

# How many times should a rndc task be retried?
RNDC_COMMAND_MAX_RETRY = 10

# How long to wait between rndc tasks retries (in seconds)?
RNDC_COMMAND_RETRY_DELAY = 2


@task(max_retries=RNDC_COMMAND_MAX_RETRY, queue=celery_config.WORKER_QUEUE_DNS)
@log_task_events()
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
@log_task_events()
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
@log_task_events()
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
@log_task_events()
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
@log_task_events()
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
@log_task_events(level=logging.DEBUG)
@log_exception_text
def upload_dhcp_leases():
    """Upload DHCP leases.

    Uploads leases to the MAAS API, using cached credentials -- the task
    originates with celerybeat, not with a server request.
    """
    upload_leases()


@task
@log_task_events()
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
        maaslog.error("add_new_dhcp_host_map failed: %s", unicode(e))
        raise


@task
@log_task_events()
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
        maaslog.error("remove_dhcp_host_map failed: %s", unicode(e))
        raise


@task
@log_task_events()
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
@log_task_events()
@log_exception_text
def restart_dhcp_server():
    """Restart the DHCP server."""
    call_and_check(['sudo', '-n', 'service', 'maas-dhcp-server', 'restart'])


# Message to put in the DHCP config file when the DHCP server gets stopped.
DISABLED_DHCP_SERVER = "# DHCP server stopped."


# Upstart issues an "Unknown instance"-type error when trying to stop an
# already-stopped service.
# A bit weird that the error message ends with colon but that's the
# error Upstart spits out.
ALREADY_STOPPED_MESSAGE = 'stop: Unknown instance:'
ALREADY_STOPPED_RETURNCODE = 1


@task
@log_task_events()
@log_exception_text
def stop_dhcp_server():
    """Write a blank config file and stop a DHCP server."""
    # Write an empty config file to avoid having an outdated config laying
    # around.
    sudo_write_file(
        celery_config.DHCP_CONFIG_FILE, DISABLED_DHCP_SERVER)
    try:
        # Use LC_ALL=C because we use the returned error message when
        # errors occur.
        call_and_check(
            ['sudo', '-n', 'service', 'maas-dhcp-server', 'stop'],
            env={'LC_ALL': 'C'}
        )
    except ExternalProcessError as error:
        # Upstart issues an "Unknown instance"-type error when trying to
        # stop an already-stopped service.  Ignore this error.
        is_already_stopped_error = (
            error.returncode == ALREADY_STOPPED_RETURNCODE and
            error.output.strip() == ALREADY_STOPPED_MESSAGE
        )
        if is_already_stopped_error:
            return
        raise


@task
@log_task_events(level=logging.DEBUG)
@log_exception_text
def periodic_probe_dhcp():
    """Probe for foreign DHCP servers."""
    detect.periodic_probe_task()


# =====================================================================
# Boot images-related tasks
# =====================================================================


@task
@log_task_events(level=logging.DEBUG)
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
@log_task_events()
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
@log_task_events()
@log_exception_text
def import_boot_images(sources, http_proxy=None, callback=None):
    for source in sources:
        # Decode any b64 keyring data to bytes.
        data = source.get("keyring_data")
        if data is not None:
            source["keyring_data"] = b64decode(data)
    variables = {
        'GNUPGHOME': MAAS_USER_GPGHOME,
        }
    if http_proxy is not None:
        variables['http_proxy'] = http_proxy
        variables['https_proxy'] = http_proxy
    with environment_variables(variables):
        boot_resources.import_images(sources)
    if callback is not None:
        callback.delay()


# =====================================================================
# Custom hardware tasks
# =====================================================================

@task
@log_task_events()
@log_exception_text
def add_seamicro15k(mac, username, password, power_control=None):
    """ See `maasserver.api.NodeGroup.add_seamicro15k`. """
    ip = find_ip_via_arp(mac)
    if ip is not None:
        probe_seamicro15k_and_enlist(
            ip, username, password,
            power_control=power_control)
    else:
        maaslog.warning("Couldn't find IP address for MAC %s" % mac)


@task
@log_task_events()
@log_exception_text
def add_virsh(poweraddr, password=None):
    """ See `maasserver.api.NodeGroup.add_virsh`. """
    probe_virsh_and_enlist(poweraddr, password=password)


@task
@log_task_events()
@log_exception_text
def enlist_nodes_from_ucsm(url, username, password):
    """ See `maasserver.api.NodeGroupHandler.enlist_nodes_from_ucsm`. """
    probe_and_enlist_ucsm(url, username, password)


@task
@log_task_events()
@log_exception_text
def enlist_nodes_from_mscm(host, username, password):
    """ See `maasserver.api.NodeGroupHandler.enlist_nodes_from_mscm`. """
    probe_and_enlist_mscm(host, username, password)

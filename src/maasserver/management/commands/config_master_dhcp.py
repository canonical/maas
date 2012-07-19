# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Configure master DHCP.

The master DHCP settings apply to the DHCP server running on the MAAS server
itself.  They can be either disabled (if you don't want MAAS to manage DHCP)
or fully configured using this command.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'Command',
    ]

from optparse import (
    make_option,
    OptionValueError,
    )

from django.core.management.base import BaseCommand
from maasserver.models import NodeGroup


dhcp_items = {
    'subnet_mask': "Subnet mask, e.g. 255.0.0.0",
    'broadcast_ip': "Broadcast address for this subnet, e.g. 10.255.255.255",
    'router_ip': "Address of default gateway.",
    'ip_range_low': "Lowest IP address to assign to clients.",
    'ip_range_high': "Highest IP address to assign to clients.",
    }


# DHCP settings when disabled.
clear_settings = {item: None for item in dhcp_items}


def get_settings(options):
    """Get the DHCP settings from `options`, as a dict.

    Checks validity of the settings.
    """
    settings = {
        item: options.get(item)
        for item in dhcp_items}
    # All of the DHCP settings must have (non-empty) values.
    if not all(settings.values()):
        raise OptionValueError(
            "Specify all DHCP settings: %s" % ', '.join(dhcp_items))
    return settings


def name_option(dhcp_setting):
    """Formulate the option name corresponding to a DHCP setting name."""
    return '--%s' % dhcp_setting.replace('_', '-')


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option(
            '--clear', dest='clear', action='store_true', default=False,
            help=(
                "Clear settings.  Do only when MAAS DHCP is disabled.  "
                "If given, any DHCP parameters are ignored.")),
        make_option(
            '--ensure', dest='ensure', action='store_true', default=False,
            help=(
                "Ensure that the master node group is configured, "
                "but if it was already set up, don't change its settings.  "
                "If given, any DHCP parameters are ignored.")),
        ) + tuple(
            make_option(
                name_option(item), dest=item, default=None,
                help="DHCP parameter: %s" % help)
            for item, help in dhcp_items.items())
    help = "Initialize master DHCP settings."

    def handle(self, *args, **options):
        if options.get('ensure') and options.get('clear'):
            raise OptionValueError(
                "The --ensure option conflicts with --clear.")
        master_nodegroup = NodeGroup.objects.ensure_master()
        if not options.get('ensure'):
            if options.get('clear'):
                settings = clear_settings
            else:
                settings = get_settings(options)
            for item, value in settings.items():
                setattr(master_nodegroup, item, value)
            master_nodegroup.save()

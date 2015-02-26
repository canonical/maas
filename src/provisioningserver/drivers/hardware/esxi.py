# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'probe_esxi_and_enlist',
    ]

from provisioningserver.drivers.hardware.virsh import (
    VirshSSH,
    VirshVMState,
    VM_STATE_TO_POWER_STATE,
    )
from provisioningserver.utils import (
    commission_node,
    create_node,
    )
from provisioningserver.utils.twisted import synchronous


class ESXiError(Exception):
    """Failure communicating to ESXi. """


def compose_esxi_url(username, password):
    return "esx://%s@%s/?no_verify=1" % (username, password)


@synchronous
def probe_esxi_and_enlist(
        user, poweraddr, password,
        prefix_filter=None, accept_all=False):
    """Extracts all of the virtual machines from virsh and enlists them
    into MAAS.

    :param user: user for the nodes.
    :param poweraddr: IP Address of ESXi host.
    :param password: password connection string.
    :param prefix_filter: only enlist nodes that have the prefix.
    :param accept_all: if True, commission enlisted nodes.
    """
    conn = VirshSSH(dom_prefix=prefix_filter)
    virsh_poweraddr = compose_esxi_url(user, poweraddr)
    if not conn.login(virsh_poweraddr, password):
        raise ESXiError('Failed to login to virsh console.')

    for machine in conn.list():
        arch = conn.get_arch(machine)
        state = conn.get_state(machine)
        macs = conn.get_mac_addresses(machine)

        # Force the machine off, as MAAS will control the machine
        # and it needs to be in a known state of off.
        if state == VirshVMState.ON:
            conn.poweroff(machine)

        params = {
            'power_address': poweraddr,
            'power_user': user,
            'power_id': machine,
            'power_pass': password,
        }
        system_id = create_node(macs, arch, 'esxi', params).wait(30)

        if accept_all:
            commission_node(system_id, user).wait(30)

    conn.logout()


def power_control_esxi(poweraddr, machine, power_change, user, password):
    """Powers controls a virtual machine using virsh."""

    conn = VirshSSH()
    virsh_poweraddr = compose_esxi_url(user, poweraddr)
    if not conn.login(virsh_poweraddr, password):
        raise ESXiError('Failed to login to virsh console.')

    state = conn.get_state(machine)
    if state is None:
        raise ESXiError('Failed to get virtual domain: %s' % machine)

    if state == VirshVMState.OFF:
        if power_change == 'on':
            if not conn.poweron(machine):
                raise ESXiError('Failed to power on domain: %s' % machine)
    elif state == VirshVMState.ON:
        if power_change == 'off':
            if not conn.poweroff(machine):
                raise ESXiError('Failed to power off domain: %s' % machine)


def power_state_esxi(poweraddr, machine, user, password):
    """Return the power state for the virtual machine using virsh."""

    conn = VirshSSH()
    virsh_poweraddr = compose_esxi_url(user, poweraddr)
    if not conn.login(virsh_poweraddr, password):
        raise ESXiError('Failed to login to virsh console.')

    state = conn.get_state(machine)
    if state is None:
        raise ESXiError('Failed to get domain: %s' % machine)

    try:
        return VM_STATE_TO_POWER_STATE[state]
    except KeyError:
        raise ESXiError('Unknown power state: %s' % state)

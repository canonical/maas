# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `network` module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from random import (
    choice,
    randint,
    )

from maastesting.factory import factory
from maastesting.testcase import TestCase
from provisioningserver import network


def make_address_line(**kwargs):
    """Create an inet address line."""
    # First word on this line is inet or inet6.
    kwargs.setdefault('inet', 'inet')
    kwargs.setdefault('broadcast', '10.255.255.255')
    kwargs.setdefault('subnet_mask', '255.0.0.0')
    items = [
        "%(inet)s addr:%(ip)s"
        ]
    if len(kwargs['broadcast']) > 0:
        items.append("Bcast:%(broadcast)s")
    items.append("Mask:%(subnet_mask)s")
    return '  '.join(items) % kwargs


def make_stats_line(direction, **kwargs):
    """Create one of the incoming/outcoming packet-count lines."""
    assert direction in {'RX', 'TX'}
    if direction == 'RX':
        variable_field = 'frame'
    else:
        variable_field = 'carrier'
    kwargs.setdefault('variable_field', variable_field)
    kwargs.setdefault('packets', randint(0, 100000))
    kwargs.setdefault('errors', randint(0, 100))
    kwargs.setdefault('dropped', randint(0, 100))
    kwargs.setdefault('overruns', randint(0, 100))
    kwargs.setdefault('variable', randint(0, 100))

    return " ".join([
        direction,
        "packets:%(packets)d",
        "errors:%(errors)d",
        "dropped:%(dropped)d",
        "overruns:%(overruns)d",
        "%(variable_field)s:%(variable)d"
        ]) % kwargs


def make_payload_stats(direction, **kwargs):
    assert direction in {'RX', 'TX'}
    kwargs.setdefault('bytes', randint(0, 1000000))
    kwargs.setdefault('bigger_unit', randint(10, 10240) / 10.0)
    kwargs.setdefault('unit', choice(['B', 'KB', 'GB']))
    return " ".join([
        direction,
        "bytes:%(bytes)s",
        "(%(bigger_unit)d %(unit)s)",
        ]) % kwargs


def make_stanza(**kwargs):
    """Create an ifconfig output stanza.

    Variable values can be specified, but will be given random values by
    default.  Values that interfaces may not have, such as broadcast
    address or allocated interrupt, may be set to the empty string to
    indicate that they should be left out of the output.
    """
    kwargs.setdefault('interface', factory.make_name('eth'))
    kwargs.setdefault('encapsulation', 'Ethernet')
    kwargs.setdefault('mac', factory.getRandomMACAddress())
    kwargs.setdefault('ip', factory.getRandomIPAddress())
    kwargs.setdefault('broadcast', factory.getRandomIPAddress())
    kwargs.setdefault('mtu', randint(100, 10000))
    kwargs.setdefault('rxline', make_stats_line('RX', **kwargs))
    kwargs.setdefault('txline', make_stats_line('TX', **kwargs))
    kwargs.setdefault('collisions', randint(0, 100))
    kwargs.setdefault('txqueuelen', randint(0, 100))
    kwargs.setdefault('rxbytes', make_payload_stats('RX', **kwargs))
    kwargs.setdefault('txbytes', make_payload_stats('TX', **kwargs))
    kwargs.setdefault('interrupt', randint(1, 30))

    # The real-life output seems to have two trailing spaces here.
    header = "%(interface)s Link encap:%(encapsulation)s  HWaddr %(mac)s  "
    body_lines = [
        "UP BROADCAST MULTICAST  MTU:%(mtu)d  Metric:1",
        ]
    if len(kwargs['ip']) > 0:
        body_lines.append(make_address_line(inet='inet', **kwargs))
    body_lines += [
        "%(rxline)s",
        "%(txline)s",
        # This line has a trailing space in the real-life output.
        "collisions:%(collisions)d txqueuelen:%(txqueuelen)d ",
        "%(rxbytes)s  %(txbytes)s",
        ]
    if kwargs['interrupt'] != '':
        body_lines.append("Interrupt:%(interrupt)d")

    text = '\n'.join(
        [header] +
        [(10 * " ") + line for line in body_lines])
    return (text + "\n") % kwargs


def join_stanzas(stanzas):
    """Format a sequence of interface stanzas like ifconfig does."""
    return '\n'.join(stanzas) + '\n'


# Tragically can't afford to indent and then dedent() this.  This output
# isn't entirely realistic: the real output has trailing spaces here and
# there, which we don't tolerate in our source code.
sample_output = """\
eth0      Link encap:Ethernet  HWaddr 00:25:bc:e6:0b:c2
          UP BROADCAST MULTICAST  MTU:1500  Metric:1
          RX packets:0 errors:0 dropped:0 overruns:0 frame:0
          TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)

eth1      Link encap:Ethernet  HWaddr 00:14:73:ad:29:62
          inet addr:192.168.12.103  Bcast:192.168.12.255  Mask:255.255.255.0
          inet6 addr: fe81::210:9ff:fcd3:6120/64 Scope:Link
          UP BROADCAST RUNNING MULTICAST  MTU:1500  Metric:1
          RX packets:5272 errors:1 dropped:0 overruns:0 frame:3274
          TX packets:5940 errors:2 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:1000
          RX bytes:2254714 (2.2 MB)  TX bytes:4045385 (4.0 MB)
          Interrupt:22

lo        Link encap:Local Loopback
          inet addr:127.0.0.1  Mask:255.0.0.0
          inet6 addr: ::1/128 Scope:Host
          UP LOOPBACK RUNNING  MTU:16436  Metric:1
          RX packets:297493 errors:0 dropped:0 overruns:0 frame:0
          TX packets:297493 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0
          RX bytes:43708 (43.7 KB)  TX bytes:43708 (43.7 KB)

maasbr0   Link encap:Ethernet  HWaddr 46:a1:20:8b:77:14
          inet addr:192.168.64.1  Bcast:192.168.64.255  Mask:255.255.255.0
          UP BROADCAST MULTICAST  MTU:1500  Metric:1
          RX packets:0 errors:0 dropped:0 overruns:0 frame:0
          TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0
          RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)

virbr0    Link encap:Ethernet  HWaddr 68:14:23:c0:6d:bf
          inet addr:192.168.80.1  Bcast:192.168.80.255  Mask:255.255.255.0
          UP BROADCAST MULTICAST  MTU:1500  Metric:1
          RX packets:0 errors:0 dropped:0 overruns:0 frame:0
          TX packets:0 errors:0 dropped:0 overruns:0 carrier:0
          collisions:0 txqueuelen:0
          RX bytes:0 (0.0 B)  TX bytes:0 (0.0 B)

    """


class TestNetworks(TestCase):

    def test_run_ifconfig_returns_ifconfig_output(self):
        text = join_stanzas([make_stanza()])
        self.patch(network, 'check_output').return_value = text.encode('ascii')
        self.assertEqual(text, network.run_ifconfig())

    def test_parse_ifconfig_produces_interface_info(self):
        num_interfaces = randint(1, 3)
        text = join_stanzas([
            make_stanza()
            for counter in range(num_interfaces)])
        info = network.parse_ifconfig(text)
        self.assertEqual(num_interfaces, len(info))
        self.assertIsInstance(info[0], network.InterfaceInfo)

    def test_parse_stanza_reads_interface_with_ip_and_interrupt(self):
        parms = {
            'interface': factory.make_name('eth'),
            'ip': factory.getRandomIPAddress(),
            'subnet_mask': '255.255.255.128',
        }
        info = network.parse_stanza(make_stanza(**parms))
        self.assertEqual(parms, info.as_dict())

    def test_parse_stanza_reads_interface_without_interrupt(self):
        parms = {
            'interface': factory.make_name('eth'),
            'ip': factory.getRandomIPAddress(),
            'subnet_mask': '255.255.255.128',
            'interrupt': '',
        }
        info = network.parse_stanza(make_stanza(**parms))
        expected = parms.copy()
        del expected['interrupt']
        self.assertEqual(expected, info.as_dict())

    def test_parse_stanza_reads_interface_without_ip(self):
        parms = {
            'interface': factory.make_name('eth'),
            'ip': '',
        }
        info = network.parse_stanza(make_stanza(**parms))
        expected = parms.copy()
        expected['ip'] = None
        expected['subnet_mask'] = None
        self.assertEqual(expected, info.as_dict())

    def test_parse_stanza_returns_nothing_for_loopback(self):
        parms = {
            'interface': 'lo',
            'ip': '127.1.2.3',
            'subnet_mask': '255.0.0.0',
            'encapsulation': 'Local Loopback',
            'broadcast': '',
            'interrupt': '',
        }
        self.assertIsNone(network.parse_stanza(make_stanza(**parms)))

    def test_split_stanzas_returns_empty_for_empty_input(self):
        self.assertEqual([], network.split_stanzas(''))

    def test_split_stanzas_returns_single_stanza(self):
        stanza = make_stanza()
        self.assertEqual([stanza.strip()], network.split_stanzas(stanza))

    def test_split_stanzas_splits_multiple_stanzas(self):
        stanzas = [make_stanza() for counter in range(3)]
        full_output = join_stanzas(stanzas)
        self.assertEqual(
            [stanza.strip() for stanza in stanzas],
            network.split_stanzas(full_output))

    def test_discover_networks_runs_in_real_life(self):
        interfaces = network.discover_networks()
        self.assertIsInstance(interfaces, list)

    def test_discover_networks_returns_suitable_interfaces(self):
        params = {
            'interface': factory.make_name('eth'),
            'ip': factory.getRandomIPAddress(),
            'subnet_mask': '255.255.255.0',
        }
        regular_interface = make_stanza(**params)
        loopback = make_stanza(
            interface='lo', encapsulation='Local loopback', broadcast='',
            interrupt='')
        disabled_interface = make_stanza(ip='', broadcast='', subnet_mask='')

        text = join_stanzas([regular_interface, loopback, disabled_interface])
        self.patch(network, 'run_ifconfig').return_value = text

        interfaces = network.discover_networks()

        self.assertEqual(
            [params],
            [interface for interface in interfaces])

    def test_discover_networks_processes_real_ifconfig_output(self):
        self.patch(network, 'run_ifconfig').return_value = sample_output
        info = network.discover_networks()
        self.assertEqual(
            ['eth1', 'maasbr0', 'virbr0'],
            [interface['interface'] for interface in info])

# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test custom commissioning scripts."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import doctest
from functools import partial
from inspect import getsource
from io import BytesIO
import json
from math import (
    ceil,
    floor,
)
import os.path
import random
from random import randint
import subprocess
from subprocess import (
    CalledProcessError,
    check_output,
    STDOUT,
)
import tarfile
from textwrap import dedent
import time

from fixtures import FakeLogger
from maasserver.fields import MAC
from maasserver.models.macaddress import MACAddress
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.tag import Tag
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import (
    MAASServerTestCase,
    TestWithoutCrochetMixin,
)
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
)
from maastesting.utils import sample_binary_data
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import Bin
from metadataserver.models import (
    CommissioningScript,
    commissioningscript as cs_module,
)
from metadataserver.models.commissioningscript import (
    ARCHIVE_PREFIX,
    extract_router_mac_addresses,
    inject_lldp_result,
    inject_lshw_result,
    inject_result,
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
    make_function_call_script,
    set_node_routers,
    set_virtual_tag,
    update_hardware_details,
    update_node_network_information,
    update_node_physical_block_devices,
)
from metadataserver.models.noderesult import NodeResult
from mock import (
    call,
    create_autospec,
    Mock,
    sentinel,
)
from testtools.content import text_content
from testtools.matchers import (
    Contains,
    ContainsAll,
    DocTestMatches,
    MatchesStructure,
    Not,
)


def open_tarfile(content):
    """Open tar file from raw binary data."""
    return tarfile.open(fileobj=BytesIO(content))


def make_script_name(base_name=None, number=None):
    """Make up a name for a commissioning script."""
    if base_name is None:
        base_name = 'script'
    if number is None:
        number = randint(0, 99)
    return factory.make_name(
        '%0.2d-%s' % (number, factory.make_name(base_name)))


class TestCommissioningScriptManager(MAASServerTestCase):

    def test_get_archive_wraps_scripts_in_tar(self):
        script = factory.make_CommissioningScript()
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertTrue(archive.getmember(path).isfile())
        self.assertEqual(script.content, archive.extractfile(path).read())

    def test_get_archive_wraps_all_scripts(self):
        scripts = {factory.make_CommissioningScript() for counter in range(3)}
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertThat(
            archive.getnames(),
            ContainsAll({
                os.path.join(ARCHIVE_PREFIX, script.name)
                for script in scripts
                }))

    def test_get_archive_supports_binary_scripts(self):
        script = factory.make_CommissioningScript(content=sample_binary_data)
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertEqual(script.content, archive.extractfile(path).read())

    def test_get_archive_includes_builtin_scripts(self):
        name = factory.make_name('00-maas')
        path = os.path.join(ARCHIVE_PREFIX, name)
        content = factory.make_string().encode('ascii')
        data = dict(name=name, content=content, hook='hook')
        self.patch(cs_module, 'BUILTIN_COMMISSIONING_SCRIPTS', {name: data})
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertIn(path, archive.getnames())
        self.assertEqual(content, archive.extractfile(path).read())

    def test_get_archive_sets_sensible_mode(self):
        for counter in range(3):
            factory.make_CommissioningScript()
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        self.assertEqual({0755}, {info.mode for info in archive.getmembers()})

    def test_get_archive_initializes_file_timestamps(self):
        # The mtime on a file inside the tarball is reasonable.
        # It would otherwise default to the Epoch, and GNU tar warns
        # annoyingly about improbably old files.
        start_time = floor(time.time())
        script = factory.make_CommissioningScript()
        path = os.path.join(ARCHIVE_PREFIX, script.name)
        archive = open_tarfile(CommissioningScript.objects.get_archive())
        timestamp = archive.getmember(path).mtime
        end_time = ceil(time.time())
        self.assertGreaterEqual(timestamp, start_time)
        self.assertLessEqual(timestamp, end_time)


class TestCommissioningScript(MAASServerTestCase):

    def test_scripts_may_be_binary(self):
        name = make_script_name()
        CommissioningScript.objects.create(
            name=name, content=Bin(sample_binary_data))
        stored_script = CommissioningScript.objects.get(name=name)
        self.assertEqual(sample_binary_data, stored_script.content)


class TestMakeFunctionCallScript(MAASServerTestCase):

    def run_script(self, script):
        script_filename = self.make_file("test.py", script)
        os.chmod(script_filename, 0700)
        try:
            return check_output((script_filename,), stderr=STDOUT)
        except CalledProcessError as error:
            self.addDetail("output", text_content(error.output))
            raise

    def test_basic(self):
        def example_function():
            print("Hello, World!", end="")
        script = make_function_call_script(example_function)
        self.assertEqual(b"Hello, World!", self.run_script(script))

    def test_positional_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, "foo", 12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_keyword_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, a="foo", b=12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_positional_and_keyword_args_get_passed_through(self):
        def example_function(a, b):
            print("a=%s, b=%d" % (a, b), end="")
        script = make_function_call_script(example_function, "foo", b=12345)
        self.assertEqual(b"a=foo, b=12345", self.run_script(script))

    def test_non_ascii_positional_args_are_passed_without_corruption(self):
        def example_function(text):
            print(repr(text), end="")
        script = make_function_call_script(example_function, "abc\u1234")
        self.assertEqual(b"u'abc\\u1234'", self.run_script(script))

    def test_non_ascii_keyword_args_are_passed_without_corruption(self):
        def example_function(text):
            print(repr(text), end="")
        script = make_function_call_script(example_function, text="abc\u1234")
        self.assertEqual(b"u'abc\\u1234'", self.run_script(script))

    def test_structured_arguments_are_passed_though_too(self):
        # Anything that can be JSON serialized can be passed.
        def example_function(arg):
            if arg == {"123": "foo", "bar": [4, 5, 6]}:
                print("Equal")
            else:
                print("Unequal, got %s" % repr(arg))
        script = make_function_call_script(
            example_function, {"123": "foo", "bar": [4, 5, 6]})
        self.assertEqual(b"Equal\n", self.run_script(script))


def isolate_function(function, namespace=None):
    """Recompile the given function in the given namespace.

    :param namespace: A dict to use as the namespace. If not provided, and
        empty namespace will be used.
    """
    source = dedent(getsource(function))
    modcode = compile(source, "isolated.py", "exec")
    namespace = {} if namespace is None else namespace
    exec(modcode, namespace)
    return namespace[function.__name__]


class TestLLDPScripts(TestWithoutCrochetMixin, MAASServerTestCase):

    def test_install_script_installs_configures_and_restarts(self):
        config_file = self.make_file("config", "# ...")
        check_call = self.patch(subprocess, "check_call")
        lldpd_install = isolate_function(cs_module.lldpd_install)
        lldpd_install(config_file)
        # lldpd is installed and restarted.
        self.assertEqual(
            check_call.call_args_list,
            [
                call(("apt-get", "install", "--yes", "lldpd")),
                call(("initctl", "reload-configuration")),
                call(("service", "lldpd", "restart"))
            ])
        # lldpd's config was updated to include an updated DAEMON_ARGS
        # setting. Note that the new comment is on a new line, and
        # does not interfere with existing config.
        config_expected = dedent("""\
            # ...
            # Configured by MAAS:
            DAEMON_ARGS="-c -f -s -e -r"
            """).encode("ascii")
        with open(config_file, "rb") as fd:
            config_observed = fd.read()
        self.assertEqual(config_expected, config_observed)

    def test_wait_script_waits_for_lldpd(self):
        reference_file = self.make_file("reference")
        time_delay = 8.98  # seconds
        lldpd_wait = isolate_function(cs_module.lldpd_wait)
        # Do the patching as late as possible, because the setup may call
        # one of the patched functions somewhere in the plumbing.  We've had
        # spurious test failures over this: bug 1283918.
        self.patch(os.path, "getmtime").return_value = 10.65
        self.patch(time, "time").return_value = 14.12
        self.patch(time, "sleep")

        lldpd_wait(reference_file, time_delay)

        # lldpd_wait checks the mtime of the reference file,
        self.assertThat(os.path.getmtime, MockCalledOnceWith(reference_file))
        # and gets the current time,
        self.assertThat(time.time, MockCalledOnceWith())
        # then sleeps until time_delay seconds has passed since the
        # mtime of the reference file.
        self.assertThat(time.sleep, MockCalledOnceWith(
            os.path.getmtime.return_value + time_delay -
            time.time.return_value))

    def test_capture_calls_lldpdctl(self):
        check_call = self.patch(subprocess, "check_call")
        lldpd_capture = isolate_function(cs_module.lldpd_capture)
        lldpd_capture()
        self.assertEqual(
            check_call.call_args_list,
            [call(("lldpctl", "-f", "xml"))])


lldp_output_template = """
<?xml version="1.0" encoding="UTF-8"?>
<lldp label="LLDP neighbors">
%s
</lldp>
"""

lldp_output_interface_template = """
<interface label="Interface" name="eth1" via="LLDP">
  <chassis label="Chassis">
    <id label="ChassisID" type="mac">%s</id>
    <name label="SysName">switch-name</name>
    <descr label="SysDescr">HDFD5BG7J</descr>
    <mgmt-ip label="MgmtIP">192.168.9.9</mgmt-ip>
    <capability label="Capability" type="Bridge" enabled="on"/>
    <capability label="Capability" type="Router" enabled="off"/>
  </chassis>
</interface>
"""


def make_lldp_output(macs):
    """Return an example raw lldp output containing the given MACs."""
    interfaces = '\n'.join(
        lldp_output_interface_template % mac
        for mac in macs
        )
    script = (lldp_output_template % interfaces).encode('utf8')
    return bytes(script)


# The two following example outputs differ because eth2 and eth1 are not
# configured and thus 'ifconfig -s -a' returns a list with both 'eth1'
# and 'eth2' while 'ifconfig -s' does not contain them.

# Example output of 'ifconfig -s -a':
ifconfig_all = """
Iface   MTU Met   RX-OK RX-ERR RX-DRP RX-OVR    TX-OK TX-ERR TX-DRP
eth2       1500 0         0      0      0 0             0      0
eth1       1500 0         0      0      0 0             0      0
eth0       1500 0   1366127      0      0 0        831110      0
lo        65536 0     38075      0      0 0         38075      0
virbr0     1500 0         0      0      0 0             0      0
wlan0      1500 0   2304695      0      0 0       1436049      0
"""

# Example output of 'ifconfig -s':
ifconfig_config = """
Iface   MTU Met   RX-OK RX-ERR RX-DRP RX-OVR    TX-OK TX-ERR TX-DRP
eth0       1500 0   1366127      0      0 0        831110      0
lo        65536 0     38115      0      0 0         38115      0
virbr0     1500 0         0      0      0 0             0      0
wlan0      1500 0   2304961      0      0 0       1436319      0
"""


class TestDHCPExplore(MAASServerTestCase):

    def test_calls_dhclient_on_unconfigured_interfaces(self):
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [ifconfig_all, ifconfig_config]
        mock_call = self.patch(subprocess, "call")
        dhcp_explore = isolate_function(cs_module.dhcp_explore)
        dhcp_explore()
        self.assertThat(
            mock_call,
            MockCallsMatch(
                call(["dhclient", "-nw", 'eth1']),
                call(["dhclient", "-nw", 'eth2'])))


class TestExtractRouters(MAASServerTestCase):

    def test_extract_router_mac_addresses_returns_None_when_empty_input(self):
        self.assertIsNone(extract_router_mac_addresses(''))

    def test_extract_router_mac_addresses_returns_empty_list(self):
        lldp_output = make_lldp_output([])
        self.assertItemsEqual([], extract_router_mac_addresses(lldp_output))

    def test_extract_router_mac_addresses_returns_routers_list(self):
        macs = ["11:22:33:44:55:66", "aa:bb:cc:dd:ee:ff"]
        lldp_output = make_lldp_output(macs)
        routers = extract_router_mac_addresses(lldp_output)
        self.assertItemsEqual(macs, routers)


class TestSetNodeRouters(MAASServerTestCase):

    def test_set_node_routers_updates_node(self):
        node = factory.make_Node(routers=None)
        macs = ["11:22:33:44:55:66", "aa:bb:cc:dd:ee:ff"]
        lldp_output = make_lldp_output(macs)
        set_node_routers(node, lldp_output, 0)
        self.assertItemsEqual(
            [MAC(mac) for mac in macs], reload_object(node).routers)

    def test_set_node_routers_updates_node_if_no_routers(self):
        node = factory.make_Node()
        lldp_output = make_lldp_output([])
        set_node_routers(node, lldp_output, 0)
        self.assertItemsEqual([], reload_object(node).routers)

    def test_set_node_routers_does_nothing_if_script_failed(self):
        node = factory.make_Node()
        routers_before = node.routers
        macs = ["11:22:33:44:55:66", "aa:bb:cc:dd:ee:ff"]
        lldp_output = make_lldp_output(macs)
        set_node_routers(node, lldp_output, exit_status=1)
        routers_after = reload_object(node).routers
        self.assertItemsEqual(routers_before, routers_after)


class TestInjectResult(MAASServerTestCase):

    def test_inject_result_stores_data(self):
        node = factory.make_Node()
        name = factory.make_name("result")
        output = factory.make_bytes()
        exit_status = next(factory.random_octets)

        inject_result(node, name, output, exit_status)

        self.assertThat(
            NodeResult.objects.get(node=node, name=name),
            MatchesStructure.byEquality(
                node=node, name=name, script_result=exit_status,
                result_type=RESULT_TYPE.COMMISSIONING,
                data=output))

    def test_inject_result_calls_hook(self):
        node = factory.make_Node()
        name = factory.make_name("result")
        output = factory.make_bytes()
        exit_status = next(factory.random_octets)
        hook = Mock()
        self.patch(
            cs_module, "BUILTIN_COMMISSIONING_SCRIPTS",
            {name: {"hook": hook}})

        inject_result(node, name, output, exit_status)

        self.assertThat(hook, MockCalledOnceWith(
            node=node, output=output, exit_status=exit_status))

    def inject_lshw_result(self):
        # inject_lshw_result() just calls through to inject_result().
        inject_result = self.patch(
            cs_module, "inject_result",
            create_autospec(cs_module.inject_result))
        inject_lshw_result(sentinel.node, sentinel.output, sentinel.status)
        self.assertThat(inject_result, MockCalledOnceWith(
            sentinel.node, LSHW_OUTPUT_NAME, sentinel.output, sentinel.status))

    def inject_lldp_result(self):
        # inject_lldp_result() just calls through to inject_result().
        inject_result = self.patch(
            cs_module, "inject_result",
            create_autospec(cs_module.inject_result))
        inject_lldp_result(sentinel.node, sentinel.output, sentinel.status)
        self.assertThat(inject_result, MockCalledOnceWith(
            sentinel.node, LLDP_OUTPUT_NAME, sentinel.output, sentinel.status))


class TestSetVirtualTag(MAASServerTestCase):

    def getVirtualTag(self):
        virtual_tag, _ = Tag.objects.get_or_create(name='virtual')
        return virtual_tag

    def assertTagsEqual(self, node, tags):
        self.assertItemsEqual(
            tags, [tag.name for tag in node.tags.all()])

    def test_sets_virtual_tag(self):
        node = factory.make_Node()
        self.assertTagsEqual(node, [])
        set_virtual_tag(node, b"virtual", 0)
        self.assertTagsEqual(node, ["virtual"])

    def test_removes_virtual_tag(self):
        node = factory.make_Node()
        node.tags.add(self.getVirtualTag())
        self.assertTagsEqual(node, ["virtual"])
        set_virtual_tag(node, b"notvirtual", 0)
        self.assertTagsEqual(node, [])

    def test_output_not_containing_virtual_does_not_set_tag(self):
        logger = self.useFixture(FakeLogger())
        node = factory.make_Node()
        self.assertTagsEqual(node, [])
        set_virtual_tag(node, b"wibble", 0)
        self.assertTagsEqual(node, [])
        self.assertIn(
            "Neither 'virtual' nor 'notvirtual' appeared in the captured "
            "VIRTUALITY_SCRIPT output for node %s.\n" % node.system_id,
            logger.output)

    def test_output_not_containing_virtual_does_not_remove_tag(self):
        logger = self.useFixture(FakeLogger())
        node = factory.make_Node()
        node.tags.add(self.getVirtualTag())
        self.assertTagsEqual(node, ["virtual"])
        set_virtual_tag(node, b"wibble", 0)
        self.assertTagsEqual(node, ["virtual"])
        self.assertIn(
            "Neither 'virtual' nor 'notvirtual' appeared in the captured "
            "VIRTUALITY_SCRIPT output for node %s.\n" % node.system_id,
            logger.output)


class TestUpdateHardwareDetails(MAASServerTestCase):

    doctest_flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE

    def test_hardware_updates_cpu_count(self):
        node = factory.make_Node()
        xmlbytes = dedent("""\
        <node id="core">
           <node id="cpu:0" class="processor"/>
           <node id="cpu:1" class="processor"/>
        </node>
        """).encode("utf-8")
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        self.assertEqual(2, node.cpu_count)

    def test_cpu_count_counts_multi_cores(self):
        node = factory.make_Node()
        xmlbytes = dedent("""\
        <node id="core">
           <node id="cpu:0" class="processor">
             <configuration>
               <setting id="cores" value="2" />
               <setting id="enabledcores" value="2" />
               <setting id="threads" value="4" />
             </configuration>
           </node>
           <node id="cpu:1" class="processor"/>
        </node>
        """).encode("utf-8")
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        self.assertEqual(5, node.cpu_count)

    def test_cpu_count_skips_disabled_cpus(self):
        node = factory.make_Node()
        xmlbytes = dedent("""\
        <node id="core">
           <node id="cpu:0" class="processor"/>
           <node id="cpu:1" disabled="true" class="processor"/>
           <node id="cpu:2" disabled="true" class="processor"/>
        </node>
        """).encode("utf-8")
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        self.assertEqual(1, node.cpu_count)

    def test_hardware_updates_memory(self):
        node = factory.make_Node()
        xmlbytes = dedent("""\
        <node id="memory">
           <size units="bytes">4294967296</size>
        </node>
        """).encode("utf-8")
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        self.assertEqual(4096, node.memory)

    def test_hardware_updates_memory_lenovo(self):
        node = factory.make_Node()
        xmlbytes = dedent("""\
        <node>
          <node id="memory:0" class="memory">
            <node id="bank:0" class="memory" handle="DMI:002D">
              <size units="bytes">4294967296</size>
            </node>
            <node id="bank:1" class="memory" handle="DMI:002E">
              <size units="bytes">3221225472</size>
            </node>
          </node>
          <node id="memory:1" class="memory">
            <node id="bank:0" class="memory" handle="DMI:002F">
              <size units="bytes">536870912</size>
            </node>
          </node>
          <node id="memory:2" class="memory"></node>
        </node>
        """).encode("utf-8")
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        mega = 2 ** 20
        expected = (4294967296 + 3221225472 + 536879812) / mega
        self.assertEqual(expected, node.memory)

    def test_hardware_updates_ignores_empty_tags(self):
        # Tags with empty definitions are ignored when
        # update_hardware_details gets called.
        factory.make_Tag(definition='')
        node = factory.make_Node()
        node.save()
        xmlbytes = '<node/>'.encode("utf-8")
        update_hardware_details(node, xmlbytes, 0)
        node = reload_object(node)
        # The real test is that update_hardware_details does not blow
        # up, see bug 1131418.
        self.assertEqual([], list(node.tags.all()))

    def test_hardware_updates_logs_invalid_xml(self):
        logger = self.useFixture(FakeLogger())
        update_hardware_details(factory.make_Node(), b"garbage", 0)
        expected_log = dedent("""\
        Invalid lshw data.
        Traceback (most recent call last):
        ...
        XMLSyntaxError: Start tag expected, '<' not found, line 1, column 1
        """)
        self.assertThat(
            logger.output, DocTestMatches(
                expected_log, self.doctest_flags))

    def test_hardware_updates_does_nothing_when_exit_status_is_not_zero(self):
        logger = self.useFixture(FakeLogger(name='commissioningscript'))
        update_hardware_details(factory.make_Node(), b"garbage", exit_status=1)
        self.assertEqual("", logger.output)


class TestGatherPhysicalBlockDevices(MAASServerTestCase):

    def make_lsblk_output(
            self, name=None, read_only=False, removable=False,
            model=None, rotary=True):
        if name is None:
            name = factory.make_name('name')
        if model is None:
            model = factory.make_name('model')
        read_only = "1" if read_only else "0"
        removable = "1" if removable else "0"
        rotary = "1" if rotary else "0"
        return 'NAME="%s" RO="%s" RM="%s" MODEL="%s" ROTA="%s"' % (
            name, read_only, removable, model, rotary)

    def make_udevadm_output(
            self, name, serial=None, sata=True, cdrom=False, dev='/dev'):
        if serial is None:
            serial = factory.make_name('serial')
        sata = "1" if sata else "0"
        output = dedent("""\
            P: /devices/pci0000:00/ata3/host2/target2:0:0/2:0:0:0/block/{name}
            N: {name}
            E: DEVNAME={dev}/{name}
            E: DEVTYPE=disk
            E: ID_ATA_SATA={sata}
            E: ID_SERIAL_SHORT={serial}
            """).format(dev=os.path.abspath(dev), name=name,
                        serial=serial, sata=sata)
        if cdrom:
            output += "E: ID_CDROM=1"
        else:
            output += "E: ID_ATA_ROTATION_RATE_RPM=5400"
        return output

    def call_gather_physical_block_devices(
            self, dev_disk_byid='/dev/disk/by-id/'):
        output = BytesIO()
        namespace = {"print": partial(print, file=output)}
        gather_physical_block_devices = isolate_function(
            cs_module.gather_physical_block_devices, namespace)
        gather_physical_block_devices(dev_disk_byid=dev_disk_byid)
        return json.loads(output.getvalue())

    def test__calls_lsblk(self):
        check_output = self.patch(subprocess, "check_output")
        check_output.return_value = ""
        self.call_gather_physical_block_devices()
        self.assertThat(check_output, MockCalledOnceWith(
            ("lsblk", "-d", "-P", "-o", "NAME,RO,RM,MODEL,ROTA")))

    def test__returns_empty_list_when_no_disks(self):
        check_output = self.patch(subprocess, "check_output")
        check_output.return_value = ""
        self.assertEquals([], self.call_gather_physical_block_devices())

    def test__calls_lsblk_then_udevadm(self):
        name = factory.make_name('name')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(
                name=name),
            self.make_udevadm_output(
                name, cdrom=True),
            ]
        self.call_gather_physical_block_devices()
        self.assertThat(check_output, MockCallsMatch(
            call(("lsblk", "-d", "-P", "-o", "NAME,RO,RM,MODEL,ROTA")),
            call(("udevadm", "info", "-q", "all", "-n", name))))

    def test__returns_empty_list_when_cdrom_only(self):
        name = factory.make_name('name')
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(
                name=name),
            self.make_udevadm_output(
                name, cdrom=True),
            ]
        self.assertEquals([], self.call_gather_physical_block_devices())

    def test__calls_lsblk_udevadm_then_blockdev(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])

        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model),
            self.make_udevadm_output(name, serial=serial),
            '%s' % size,
            '%s' % block_size,
            ]
        self.call_gather_physical_block_devices()
        self.assertThat(check_output, MockCallsMatch(
            call(("lsblk", "-d", "-P", "-o", "NAME,RO,RM,MODEL,ROTA")),
            call(("udevadm", "info", "-q", "all", "-n", name)),
            call(("blockdev", "--getsize64", "/dev/%s" % name)),
            call(("blockdev", "--getbsz", "/dev/%s" % name))))

    def test__returns_block_device(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")

        # Create simulated /dev tree
        devroot = self.make_dir()
        os.mkdir(os.path.join(devroot, 'disk'))
        byidroot = os.path.join(devroot, 'disk', 'by_id')
        os.mkdir(byidroot)
        os.mknod(os.path.join(devroot, name))
        os.symlink(os.path.join(devroot, name),
                   os.path.join(byidroot, 'deviceid'))

        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model),
            self.make_udevadm_output(name, serial=serial, dev=devroot),
            '%s' % size,
            '%s' % block_size,
            ]
        self.assertEquals([{
            "NAME": name,
            "PATH": os.path.join(devroot, name),
            "ID_PATH": os.path.join(byidroot, 'deviceid'),
            "RO": "0",
            "RM": "0",
            "MODEL": model,
            "ROTA": "1",
            "SATA": "1",
            "SERIAL": serial,
            "SIZE": "%s" % size,
            "BLOCK_SIZE": "%s" % block_size,
            "RPM": "5400",
            }], self.call_gather_physical_block_devices(byidroot))

    def test__returns_block_device_without_id_path(self):
        """Block devices without by-id links should not have ID_PATH key"""
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")

        # Create simulated /dev tree without by-id link
        devroot = self.make_dir()
        os.mkdir(os.path.join(devroot, 'disk'))
        byidroot = os.path.join(devroot, 'disk', 'by_id')
        os.mkdir(byidroot)
        os.mknod(os.path.join(devroot, name))

        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model),
            self.make_udevadm_output(name, serial=serial, dev=devroot),
            '%s' % size,
            '%s' % block_size,
            ]
        self.assertEquals([{
            "NAME": name,
            "PATH": os.path.join(devroot, name),
            "RO": "0",
            "RM": "0",
            "MODEL": model,
            "ROTA": "1",
            "SATA": "1",
            "SERIAL": serial,
            "SIZE": "%s" % size,
            "BLOCK_SIZE": "%s" % block_size,
            "RPM": "5400",
            }], self.call_gather_physical_block_devices(byidroot))

    def test__returns_block_device_readonly(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model, read_only=True),
            self.make_udevadm_output(name, serial=serial),
            '%s' % size,
            '%s' % block_size,
            ]
        self.assertEquals([{
            "NAME": name,
            "PATH": "/dev/%s" % name,
            "RO": "1",
            "RM": "0",
            "MODEL": model,
            "ROTA": "1",
            "SATA": "1",
            "SERIAL": serial,
            "SIZE": "%s" % size,
            "BLOCK_SIZE": "%s" % block_size,
            "RPM": "5400",
            }], self.call_gather_physical_block_devices())

    def test__returns_block_device_ssd(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model, rotary=False),
            self.make_udevadm_output(name, serial=serial),
            '%s' % size,
            '%s' % block_size,
            ]
        self.assertEquals([{
            "NAME": name,
            "PATH": "/dev/%s" % name,
            "RO": "0",
            "RM": "0",
            "MODEL": model,
            "ROTA": "0",
            "SATA": "1",
            "SERIAL": serial,
            "SIZE": "%s" % size,
            "BLOCK_SIZE": "%s" % block_size,
            "RPM": "5400",
            }], self.call_gather_physical_block_devices())

    def test__returns_block_device_not_sata(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model),
            self.make_udevadm_output(name, serial=serial, sata=False),
            '%s' % size,
            '%s' % block_size,
            ]
        self.assertEquals([{
            "NAME": name,
            "PATH": "/dev/%s" % name,
            "RO": "0",
            "RM": "0",
            "MODEL": model,
            "ROTA": "1",
            "SATA": "0",
            "SERIAL": serial,
            "SIZE": "%s" % size,
            "BLOCK_SIZE": "%s" % block_size,
            "RPM": "5400",
            }], self.call_gather_physical_block_devices())

    def test__returns_block_device_removable(self):
        name = factory.make_name('name')
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = [
            self.make_lsblk_output(name=name, model=model, removable=True),
            self.make_udevadm_output(name, serial=serial),
            '%s' % size,
            '%s' % block_size,
            ]
        self.assertEquals([{
            "NAME": name,
            "PATH": "/dev/%s" % name,
            "RO": "0",
            "RM": "1",
            "MODEL": model,
            "ROTA": "1",
            "SATA": "1",
            "SERIAL": serial,
            "SIZE": "%s" % size,
            "BLOCK_SIZE": "%s" % block_size,
            "RPM": "5400",
            }], self.call_gather_physical_block_devices())

    def test__returns_multiple_block_devices_in_order(self):
        names = [factory.make_name('name') for _ in range(3)]
        lsblk = [
            self.make_lsblk_output(name=name)
            for name in names
            ]
        call_outputs = []
        call_outputs.append("\n".join(lsblk))
        for name in names:
            call_outputs.append(self.make_udevadm_output(name))
        for name in names:
            call_outputs.append(
                "%s" % random.randint(1000 * 1000, 1000 * 1000 * 1000))
            call_outputs.append(
                "%s" % random.choice([512, 1024, 4096]))
        check_output = self.patch(subprocess, "check_output")
        check_output.side_effect = call_outputs
        device_names = [
            block_info['NAME']
            for block_info in self.call_gather_physical_block_devices()
            ]
        self.assertEquals(names, device_names)


class TestUpdateNodePhysicalBlockDevices(MAASServerTestCase):

    def make_block_device(
            self, name=None, path=None, id_path=None, size=None,
            block_size=None, model=None, serial=None, rotary=True, rpm=None,
            removable=False, sata=False):
        if name is None:
            name = factory.make_name('name')
        if path is None:
            path = '/dev/%s' % name
        if id_path is None:
            id_path = '/dev/disk/by-id/deviceid'
        if size is None:
            size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if model is None:
            model = factory.make_name('model')
        if serial is None:
            serial = factory.make_name('serial')
        if rpm is None:
            rpm = random.choice(('4800', '5400', '10000', '15000'))
        return {
            "NAME": name,
            "PATH": path,
            "ID_PATH": id_path,
            "SIZE": '%s' % size,
            "BLOCK_SIZE": '%s' % block_size,
            "MODEL": model,
            "SERIAL": serial,
            "RO": "0",
            "RM": "1" if removable else "0",
            "ROTA": "1" if rotary else "0",
            "SATA": "1" if sata else "0",
            "RPM": "0" if not rotary else rpm
            }

    def test__does_nothing_when_exit_status_is_not_zero(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        update_node_physical_block_devices(node, b"garbage", exit_status=1)
        self.assertIsNotNone(reload_object(block_device))

    def test__clears_previous_physical_block_devices(self):
        node = factory.make_Node()
        block_device = factory.make_PhysicalBlockDevice(node=node)
        update_node_physical_block_devices(node, b"[]", 0)
        self.assertIsNone(reload_object(block_device))

    def test__creates_physical_block_devices(self):
        devices = [self.make_block_device() for _ in range(3)]
        device_names = [device['NAME'] for device in devices]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        created_names = [
            device.name
            for device in PhysicalBlockDevice.objects.filter(node=node)
            ]
        self.assertItemsEqual(device_names, created_names)

    def test__creates_physical_block_devices_in_order(self):
        devices = [self.make_block_device() for _ in range(3)]
        device_names = [device['NAME'] for device in devices]
        node = factory.make_Node()
        json_output = json.dumps(devices).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        created_names = [
            device.name
            for device in (
                PhysicalBlockDevice.objects.filter(node=node).order_by('id'))
            ]
        self.assertEquals(device_names, created_names)

    def test__creates_physical_block_device(self):
        name = factory.make_name('name')
        path = '/dev/%s' % name
        id_path = '/dev/disk/by-id/deviceid'
        size = random.randint(1000 * 1000, 1000 * 1000 * 1000)
        block_size = random.choice([512, 1024, 4096])
        model = factory.make_name('model')
        serial = factory.make_name('serial')
        device = self.make_block_device(
            name=name, path=path, size=size, block_size=block_size,
            model=model, serial=serial)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first(),
            MatchesStructure.byEquality(
                name=name, path=path, id_path=id_path, size=size,
                block_size=block_size, model=model, serial=serial))

    def test__creates_physical_block_device_only_for_node(self):
        device = self.make_block_device()
        node = factory.make_Node()
        other_node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertEquals(
            0, PhysicalBlockDevice.objects.filter(node=other_node).count(),
            "Created physical block device for the incorrect node.")

    def test__creates_physical_block_device_with_rotary_tag(self):
        device = self.make_block_device(rotary=True)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('rotary'))
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('ssd')))

    def test__creates_physical_block_device_with_rotary_and_rpm_tags(self):
        device = self.make_block_device(rotary=True, rpm=5400)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('rotary'))
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('5400rpm'))

    def test__creates_physical_block_device_with_ssd_tag(self):
        device = self.make_block_device(rotary=False)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            ContainsAll(['ssd']))
        self.expectThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('rotary')))

    def test__creates_physical_block_device_without_removable_tag(self):
        device = self.make_block_device(removable=False)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('removable')))

    def test__creates_physical_block_device_with_removable_tag(self):
        device = self.make_block_device(removable=True)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('removable'))

    def test__creates_physical_block_device_without_sata_tag(self):
        device = self.make_block_device(sata=False)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Not(Contains('sata')))

    def test__creates_physical_block_device_with_sata_tag(self):
        device = self.make_block_device(sata=True)
        node = factory.make_Node()
        json_output = json.dumps([device]).encode('utf-8')
        update_node_physical_block_devices(node, json_output, 0)
        self.assertThat(
            PhysicalBlockDevice.objects.filter(node=node).first().tags,
            Contains('sata'))


class TestUpdateNodeNetworkInformation(MAASServerTestCase):
    """Tests the update_node_network_information function using data from the
    ip_link_results.txt file to simulate `ip link`'s output.

    The file records 6 different MAC addresses coming from different kinds of
    interfaces:

    38:b1:db:cd:f0:ab
    52:54:00:03:53:aa
    52:54:00:67:f5:3a
    ec:f4:bb:f9:17:8e
    fe:54:00:02:36:19
    fe:54:00:b4:f1:61
    """

    def test__add_all_interfaces(self):
        """Test a node that has no previously known interfaces on which we
        need to add a series of interfaces.
        """
        node = factory.make_Node()
        # Delete all MAC addresses eventually created by factory attached to
        # this node.
        MACAddress.objects.filter(node_id=node.id).delete()

        output = open(
            os.path.dirname(__file__) + '/ip_link_results.txt').read()
        update_node_network_information(node, output, 0)

        # Makes sure all the test dataset MAC addresses were added to the node.
        node_macaddresses = [m.mac_address for m in node.macaddress_set.all()]
        self.assertIn(MAC("38:b1:db:cd:f0:ab"), node_macaddresses)
        self.assertIn(MAC("52:54:00:03:53:aa"), node_macaddresses)
        self.assertIn(MAC("52:54:00:67:f5:3a"), node_macaddresses)
        self.assertIn(MAC("ec:f4:bb:f9:17:8e"), node_macaddresses)
        self.assertIn(MAC("fe:54:00:02:36:19"), node_macaddresses)
        self.assertIn(MAC("fe:54:00:b4:f1:61"), node_macaddresses)

    def test__one_mac_missing(self):
        """Test whether we correcly detach a NIC that no longer appears to be
        connected to the node.
        """
        node = factory.make_Node()

        # Create a MAC address that we know is not in the test dataset.
        mac_to_be_detached = factory.make_MACAddress(node=node)
        mac_to_be_detached.mac_address = "01:23:45:67:89:ab"
        mac_to_be_detached.save()

        output = open(
            os.path.dirname(__file__) + '/ip_link_results.txt').read()
        update_node_network_information(node, output, 0)
        db_macaddresses = [m.mac_address for m in node.macaddress_set.all()]

        # These should have been added to the node.
        self.assertIn(MAC("38:b1:db:cd:f0:ab"), db_macaddresses)
        self.assertIn(MAC("52:54:00:03:53:aa"), db_macaddresses)
        self.assertIn(MAC("52:54:00:67:f5:3a"), db_macaddresses)
        self.assertIn(MAC("ec:f4:bb:f9:17:8e"), db_macaddresses)
        self.assertIn(MAC("fe:54:00:02:36:19"), db_macaddresses)
        self.assertIn(MAC("fe:54:00:b4:f1:61"), db_macaddresses)

        # This one should have been removed because it no longer shows on the
        # `ip link` output.
        self.assertNotIn(MAC('01:23:45:67:89:ab'), db_macaddresses)

    def test__reassign_mac(self):
        """Test whether we can assign a MAC address previously connected to a
        different node to the current one"""
        node1 = factory.make_Node()

        # Create a MAC address that we know IS in the test dataset.
        mac_to_be_reassigned = factory.make_MACAddress(node=node1)
        mac_to_be_reassigned.mac_address = MAC('38:b1:db:cd:f0:ab')
        mac_to_be_reassigned.save()

        node2 = factory.make_Node()
        output = open(
            os.path.dirname(__file__) + '/ip_link_results.txt').read()
        update_node_network_information(node2, output, 0)

        node2_db_macaddresses = [m.mac_address
                                 for m in node2.macaddress_set.all()]
        self.assertIn(MAC("38:b1:db:cd:f0:ab"), node2_db_macaddresses)
        self.assertIn(MAC("52:54:00:03:53:aa"), node2_db_macaddresses)
        self.assertIn(MAC("52:54:00:67:f5:3a"), node2_db_macaddresses)
        self.assertIn(MAC("ec:f4:bb:f9:17:8e"), node2_db_macaddresses)
        self.assertIn(MAC("fe:54:00:02:36:19"), node2_db_macaddresses)
        self.assertIn(MAC("fe:54:00:b4:f1:61"), node2_db_macaddresses)

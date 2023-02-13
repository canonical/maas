# Copyright 2014-2016 Canonical Ltd.
# Copyright 2014 Cloudbase Solutions SRL.
# This software is licensed under the GNU Affero General Public License
# version 3 (see the file LICENSE).

"""Tests for `provisioningserver.boot.windows`."""


import io
import os
import shutil
from unittest import mock
from unittest.mock import ANY, sentinel

from tftp.backend import FilesystemReader
from twisted.internet.defer import inlineCallbacks

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from maastesting.twisted import (
    always_fail_with,
    always_succeed_with,
    extract_result,
)
from provisioningserver.boot import BootMethodError, BytesReader
from provisioningserver.boot import windows as windows_module
from provisioningserver.boot.windows import Bcd, WindowsPXEBootMethod
from provisioningserver.rpc.exceptions import NoSuchNode
from provisioningserver.rpc.region import RequestNodeInfoByMACAddress
from provisioningserver.testing.config import ClusterConfigurationFixture
from provisioningserver.tests.test_kernel_opts import make_kernel_parameters

TIMEOUT = get_testing_timeout()


class TestBcd(MAASTestCase):
    def configure_hivex(self):
        mock_hivex = mock.MagicMock()
        self.patch(windows_module, "load_hivex").return_value = mock_hivex
        mock_hivex.node_name.side_effect = [
            "Objects",
            Bcd.GUID_WINDOWS_BOOTMGR,
            Bcd.BOOT_MGR_DISPLAY_ORDER,
        ]
        mock_hivex.node_children.side_effect = [
            [factory.make_name("objects")],
            [factory.make_name("object")],
            ["value0", factory.make_UUID()],
            [factory.make_name("element")],
        ]
        mock_hivex.node_values.return_value = [factory.make_name("val")]

    def configure_bcd(self, uids=None):
        self.configure_hivex()
        filename = factory.make_name("filename")
        bcd = Bcd(filename)
        bcd.uids = mock.MagicMock(spec=dict)
        if uids is None:
            uids = [factory.make_name("uid"), factory.make_name("uid")]
        bcd.uids.__getitem__.return_value = uids
        bcd.hive = mock.MagicMock()
        return bcd

    def test_get_loader(self):
        bcd = self.configure_bcd()

        mock_elem = factory.make_name("elem")
        bootmgr_elems = mock.MagicMock(spec=dict)
        bootmgr_elems.__getitem__.return_value = mock_elem

        mock_node_value = factory.make_name("node_value")
        bcd.hive.node_values.return_value = [mock_node_value]
        mock_string = factory.make_name("strings")
        bcd.hive.value_multiple_strings.return_value = [mock_string]

        response = bcd._get_loader(bootmgr_elems)
        self.assertThat(bcd.hive.node_values, MockCalledOnceWith(mock_elem))
        self.assertThat(
            bcd.hive.value_multiple_strings,
            MockCalledOnceWith(mock_node_value),
        )
        self.assertEqual(mock_string, response)

    def test_get_loader_elems(self):
        mock_uid_0 = factory.make_name("uid")
        mock_uid_1 = factory.make_name("uid")
        bcd = self.configure_bcd(uids=[mock_uid_0, mock_uid_1])

        mock_child = factory.make_name("child")
        bcd.hive.node_children.side_effect = [[mock_child]]
        mock_name = factory.make_name("name")
        bcd.hive.node_name.return_value = mock_name

        response = bcd._get_loader_elems()
        self.assertThat(bcd.hive.node_children, MockCalledOnceWith(mock_uid_1))
        self.assertThat(bcd.hive.node_name, MockCalledOnceWith(mock_child))
        self.assertEqual(response, {mock_name: mock_child})

    def test_get_load_options_key(self):
        bcd = self.configure_bcd()

        fake_load_elem = factory.make_name("load_elem")
        mock_load_elem = mock.MagicMock()
        mock_load_elem.get.return_value = fake_load_elem

        mock_get_loader_elems = self.patch(Bcd, "_get_loader_elems")
        mock_get_loader_elems.return_value = mock_load_elem

        response = bcd._get_load_options_key()
        self.assertThat(mock_get_loader_elems, MockCalledOnceWith())
        self.assertThat(
            mock_load_elem.get, MockCalledOnceWith(bcd.LOAD_OPTIONS, None)
        )
        self.assertEqual(response, fake_load_elem)

    def test_set_load_options(self):
        mock_uid_0 = factory.make_name("uid")
        mock_uid_1 = factory.make_name("uid")
        bcd = self.configure_bcd(uids=[mock_uid_0, mock_uid_1])

        fake_value = factory.make_name("value").encode("ascii")
        mock_get_load_options_key = self.patch(Bcd, "_get_load_options_key")
        mock_get_load_options_key.return_value = None

        fake_child = factory.make_name("child")
        bcd.hive.node_add_child.return_value = fake_child
        bcd.set_load_options(value=fake_value)

        compare = {
            "t": 1,
            "key": "Element",
            "value": fake_value.decode("utf-8").encode("utf-16le"),
        }
        self.assertThat(mock_get_load_options_key, MockCalledOnceWith())
        self.assertThat(
            bcd.hive.node_add_child,
            MockCalledOnceWith(mock_uid_1, bcd.LOAD_OPTIONS),
        )
        self.assertThat(
            bcd.hive.node_set_value, MockCalledOnceWith(fake_child, compare)
        )
        self.assertThat(bcd.hive.commit, MockCalledOnceWith(None))


class TestRequestNodeInfoByMACAddress(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def test_returns_None_when_MAC_is_None(self):
        d = windows_module.request_node_info_by_mac_address(None)
        self.assertIsNone(extract_result(d))

    def test_returns_None_when_node_not_found(self):
        client = self.patch(windows_module, "getRegionClient").return_value
        client.side_effect = always_fail_with(NoSuchNode())
        mac = factory.make_mac_address()
        d = windows_module.request_node_info_by_mac_address(mac)
        self.assertIsNone(extract_result(d))

    def test_returns_output_from_RequestNodeInfoByMACAddress(self):
        client = self.patch(windows_module, "getRegionClient").return_value
        client.side_effect = always_succeed_with(sentinel.node_info)
        d = windows_module.request_node_info_by_mac_address(sentinel.mac)
        self.assertIs(extract_result(d), sentinel.node_info)
        self.assertThat(
            client,
            MockCalledOnceWith(
                RequestNodeInfoByMACAddress, mac_address=sentinel.mac
            ),
        )


class TestWindowsPXEBootMethod(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        self.patch(windows_module, "get_hivex_module")
        super().setUp()

    def test_clean_path(self):
        method = WindowsPXEBootMethod()
        parts = [factory.make_string() for _ in range(3)]
        dirty_path = "\\".join(parts)
        valid_path = dirty_path.lower().replace("\\", "/")
        clean_path = method.clean_path(dirty_path)
        self.assertEqual(valid_path, clean_path)

    def test_clean_path_strip_boot(self):
        method = WindowsPXEBootMethod()
        dirty_path = "\\Boot\\BCD"
        clean_path = method.clean_path(dirty_path)
        self.assertEqual("bcd", clean_path)

    def test_get_node_info(self):
        method = WindowsPXEBootMethod()
        mac = factory.make_mac_address()
        self.patch(windows_module, "get_remote_mac").return_value = mac
        mock_request_node_info = self.patch(
            windows_module, "request_node_info_by_mac_address"
        )
        method.get_node_info()
        self.assertThat(mock_request_node_info, MockCalledOnceWith(mac))

    @inlineCallbacks
    def test_match_path_pxelinux(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": "install",
            "osystem": "windows",
            "mac": mock_mac,
        }

        params = yield method.match_path(None, "pxelinux.0")
        self.assertEqual(mock_mac, params["mac"])
        self.assertEqual(method.bootloader_path, params["path"])

    @inlineCallbacks
    def test_match_path_pxelinux_only_on_install(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": factory.make_string(),
            "osystem": "windows",
            "mac": mock_mac,
        }

        params = yield method.match_path(None, "pxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_pxelinux_missing_hivex(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": factory.make_string(),
            "osystem": "windows",
            "mac": mock_mac,
        }

        self.patch(windows_module, "HAVE_HIVEX")
        params = yield method.match_path(None, "pxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_pxelinux_only_on_windows(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": "install",
            "osystem": factory.make_string(),
            "mac": mock_mac,
        }

        params = yield method.match_path(None, "pxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_pxelinux_get_node_info_None(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = None

        params = yield method.match_path(None, "pxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_lpxelinux(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": "install",
            "osystem": "windows",
            "mac": mock_mac,
        }

        params = yield method.match_path(None, "lpxelinux.0")
        self.assertEqual(mock_mac, params["mac"])
        self.assertEqual(method.bootloader_path, params["path"])

    @inlineCallbacks
    def test_match_path_lpxelinux_only_on_install(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": factory.make_string(),
            "osystem": "windows",
            "mac": mock_mac,
        }

        params = yield method.match_path(None, "lpxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_lpxelinux_missing_hivex(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": factory.make_string(),
            "osystem": "windows",
            "mac": mock_mac,
        }

        self.patch(windows_module, "HAVE_HIVEX")
        params = yield method.match_path(None, "lpxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_lpxelinux_only_on_windows(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = {
            "purpose": "install",
            "osystem": factory.make_string(),
            "mac": mock_mac,
        }

        params = yield method.match_path(None, "lpxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_lpxelinux_get_node_info_None(self):
        method = WindowsPXEBootMethod()
        method.remote_path = factory.make_string()
        mock_get_node_info = self.patch(method, "get_node_info")
        mock_get_node_info.return_value = None

        params = yield method.match_path(None, "lpxelinux.0")
        self.assertIsNone(params)

    @inlineCallbacks
    def test_match_path_static_file(self):
        method = WindowsPXEBootMethod()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(windows_module, "get_remote_mac")
        mock_get_node_info.return_value = mock_mac

        params = yield method.match_path(None, "bootmgr.exe")
        self.assertEqual(mock_mac, params["mac"])
        self.assertEqual("bootmgr.exe", params["path"])

    @inlineCallbacks
    def test_match_path_static_file_clean_path(self):
        method = WindowsPXEBootMethod()
        mock_mac = factory.make_mac_address()
        mock_get_node_info = self.patch(windows_module, "get_remote_mac")
        mock_get_node_info.return_value = mock_mac

        params = yield method.match_path(None, "\\Boot\\BCD")
        self.assertEqual(mock_mac, params["mac"])
        self.assertEqual("bcd", params["path"])

    def test_get_reader_bcd(self):
        method = WindowsPXEBootMethod()
        mock_compose_bcd = self.patch(method, "compose_bcd")
        local_host = factory.make_ipv4_address()
        kernel_params = make_kernel_parameters(osystem="windows")

        method.get_reader(
            None, kernel_params, path="bcd", local_host=local_host
        )
        self.assertThat(
            mock_compose_bcd, MockCalledOnceWith(kernel_params, local_host)
        )

    def test_get_reader_static_file(self):
        method = WindowsPXEBootMethod()
        mock_path = factory.make_name("path")
        mock_output_static = self.patch(method, "output_static")
        kernel_params = make_kernel_parameters(osystem="windows")

        method.get_reader(None, kernel_params, path=mock_path)
        self.assertThat(
            mock_output_static, MockCalledOnceWith(kernel_params, mock_path)
        )

    def test_compose_preseed_url(self):
        url = "http://localhost/MAAS"
        expected = "http:\\\\localhost\\^M^A^A^S"
        method = WindowsPXEBootMethod()
        output = method.compose_preseed_url(url)
        self.assertEqual(expected, output)

    def test_compose_bcd(self):
        method = WindowsPXEBootMethod()
        local_host = factory.make_ipv4_address()
        kernel_params = make_kernel_parameters()

        fake_output = factory.make_string().encode("utf-8")
        self.patch(os.path, "isfile").return_value = True
        self.patch(shutil, "copyfile")
        self.patch(windows_module, "Bcd")

        # https://bugs.python.org/issue23004 -- mock_open() should allow
        # reading binary data -- prevents the use of mock_open() here.
        self.patch(windows_module, "open")
        windows_module.open.return_value = io.BytesIO(fake_output)
        output = method.compose_bcd(kernel_params, local_host)
        self.assertThat(windows_module.open, MockCalledOnceWith(ANY, "rb"))

        self.assertTrue(isinstance(output, BytesReader))
        self.assertEqual(fake_output, output.read(-1))

    def test_compose_bcd_missing_template(self):
        method = WindowsPXEBootMethod()
        self.patch(method, "get_resource_path").return_value = ""
        local_host = factory.make_ipv4_address()
        kernel_params = make_kernel_parameters()

        self.assertRaises(
            BootMethodError, method.compose_bcd, kernel_params, local_host
        )

    def test_get_resouce_path(self):
        fake_tftproot = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=fake_tftproot))
        method = WindowsPXEBootMethod()
        fake_path = factory.make_name("path")
        fake_kernelparams = make_kernel_parameters()
        result = method.get_resource_path(fake_kernelparams, fake_path)
        expected = os.path.join(
            fake_tftproot,
            "windows",
            fake_kernelparams.arch,
            fake_kernelparams.subarch,
            fake_kernelparams.release,
            fake_kernelparams.label,
            fake_path,
        )
        self.assertEqual(expected, result)

    def test_output_static(self):
        method = WindowsPXEBootMethod()
        contents = factory.make_bytes()
        temp_dir = self.make_dir()
        filename = factory.make_file(temp_dir, "resource", contents=contents)
        self.patch(method, "get_resource_path").return_value = filename
        result = method.output_static(None, None)
        self.assertIsInstance(result, FilesystemReader)
        self.assertEqual(contents, result.read(10000))

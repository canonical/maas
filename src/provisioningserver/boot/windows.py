# Copyright 2014-2021 Canonical Ltd.
# Copyright 2014 Cloudbase Solutions SRL.
# This software is licensed under the GNU Affero General Public License
# version 3 (see the file LICENSE).

"""Windows PXE Boot Method"""

import os.path
import re
import shutil
import sys

from tftp.backend import FilesystemReader
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.python.filepath import FilePath

from maascommon.bootmethods import WindowsPXEBootMetadata
from provisioningserver.boot import (
    BootMethod,
    BootMethodError,
    BytesReader,
    get_remote_mac,
)
from provisioningserver.config import ClusterConfiguration
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.exceptions import NoSuchNode
from provisioningserver.rpc.region import RequestNodeInfoByMACAddress
from provisioningserver.utils import tftp
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.twisted import asynchronous, deferred

maaslog = get_maas_logger("windows")


# These files do not exist in the tftproot. WindowsPXEBootMethod
# handles access to these files returning the correct version
# of the file for the booting version of Windows.
#
# Note: Each version of Windows can have different content for
# these files.
STATIC_FILES = [
    "pxeboot.0",
    "bootmgr.exe",
    "\\boot\\bcd",
    "\\boot\\winpe.wim",
    "\\boot\\boot.sdi",
    "\\boot\\font\\wgl4_boot.ttf",
]


def get_hivex_module():
    """Returns the hivex module if avaliable.

    python-hivex is an optional dependency, but it is needed
    before MAAS can boot Windows.
    """
    if "hivex" not in sys.modules:
        try:
            __import__("hivex")
        except ImportError:
            return None
    return sys.modules["hivex"]


def load_hivex(*args, **kwargs):
    """Returns the Hivex object."""
    module = get_hivex_module()
    if module is None:
        return None
    return module.Hivex(*args, **kwargs)


@asynchronous
def request_node_info_by_mac_address(mac_address):
    """Request node info for the given mac address.

    :param mac_address: The MAC Address of the node of the event.
    :type mac_address: unicode
    """
    if mac_address is None:
        return succeed(None)

    client = getRegionClient()
    d = client(RequestNodeInfoByMACAddress, mac_address=mac_address)

    def eb_request_node_info(failure):
        failure.trap(NoSuchNode)
        return None

    return d.addErrback(eb_request_node_info)


class Bcd:
    """Allows modification of the load options in a Windows boot
    configuration data file.

    References:
        http://msdn.microsoft.com/en-us/library/windows/desktop/
            - aa362652(v=vs.85).aspx
            - aa362641(v=vs.85).aspx
    """

    GUID_WINDOWS_BOOTMGR = "{9dea862c-5cdd-4e70-acc1-f32b344d4795}"
    BOOT_MGR_DISPLAY_ORDER = "24000001"
    LOAD_OPTIONS = "12000030"

    def __init__(self, filename):
        self.hive = load_hivex(filename, write=True)

        # uids
        objects = self._get_root_objects()
        self.uids = {}
        for i in self.hive.node_children(objects):
            self.uids[self.hive.node_name(i)] = self.hive.node_children(i)

        # default bootloader
        mgr = self.uids[self.GUID_WINDOWS_BOOTMGR][1]
        bootmgr_elems = {
            self.hive.node_name(i): i for i in self.hive.node_children(mgr)
        }
        self.loader = self._get_loader(bootmgr_elems)

    def _get_root_elements(self):
        """Gets the root from the hive."""
        root = self.hive.root()
        r_elems = {}
        for i in self.hive.node_children(root):
            name = self.hive.node_name(i)
            r_elems[name] = i
        return r_elems

    def _get_root_objects(self):
        """Gets the root objects."""
        elems = self._get_root_elements()
        return elems["Objects"]

    def _get_loader(self, bootmgr_elems):
        """Get default bootloader."""
        (val,) = self.hive.node_values(
            bootmgr_elems[self.BOOT_MGR_DISPLAY_ORDER]
        )
        loader = self.hive.value_multiple_strings(val)[0]
        return loader

    def _get_loader_elems(self):
        """Get elements present in default boot loader. We need this
        in order to determine the loadoptions key.
        """
        return {
            self.hive.node_name(i): i
            for i in self.hive.node_children(self.uids[self.loader][1])
        }

    def _get_load_options_key(self):
        """Gets the key containing the load options we want to edit."""
        load_elem = self._get_loader_elems()
        load_option_key = load_elem.get(self.LOAD_OPTIONS, None)
        return load_option_key

    def set_load_options(self, value):
        """Sets the loadoptions value to param:value."""
        h = self._get_load_options_key()
        if h is None:
            # No load options key in the hive, add the key
            # so the value can be set.
            h = self.hive.node_add_child(
                self.uids[self.loader][1], self.LOAD_OPTIONS
            )
        k_type = 1
        key = "Element"
        data = {
            "t": k_type,
            "key": key,
            # Windows only accepts utf-16le in load options.
            "value": value.decode("utf-8").encode("utf-16le"),
        }
        self.hive.node_set_value(h, data)
        self.hive.commit(None)


class WindowsPXEBootMethod(BootMethod, WindowsPXEBootMetadata):
    @deferred
    def get_node_info(self):
        """Gets node information via the remote mac."""
        remote_mac = get_remote_mac()
        return request_node_info_by_mac_address(remote_mac)

    def clean_path(self, path):
        """Converts Windows path into a unix path and strips the
        boot subdirectory from the paths.
        """
        path = path.lower().replace("\\", "/")
        if path[0:6] == "/boot/":
            path = path[6:]
        return path

    @inlineCallbacks
    def match_path(self, backend, path):
        """Checks path to see if the boot method should handle
        the requested file.

        :param backend: requesting backend
        :param path: requested path
        :return: dict of match params from path, None if no match
        """
        # If the node is requesting the initial bootloader, then we
        # need to see if this node is set to boot Windows first.
        local_host, local_port = tftp.get_local_address()
        if path in ["pxelinux.0", "lpxelinux.0"]:
            data = yield self.get_node_info()
            if data is None:
                return None

            # Only provide the Windows bootloader when installing
            # PXELINUX chainloading will work for the rest of the time.
            purpose = data.get("purpose")
            if purpose != "install":
                return None

            osystem = data.get("osystem")
            if osystem == "windows":
                # python-hivex is needed to continue.
                if get_hivex_module() is None:
                    raise BootMethodError("python-hivex package is missing.")

                return {
                    "mac": data.get("mac"),
                    "path": self.bootloader_path,
                    "local_host": local_host,
                }
        # Fix the paths for the other static files, Windows requests.
        elif path.lower() in STATIC_FILES:
            return {
                "mac": get_remote_mac(),
                "path": self.clean_path(path),
                "local_host": local_host,
            }

    def get_reader(self, backend, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """
        path = extra["path"]
        if path == "bcd":
            local_host = extra["local_host"]
            return self.compose_bcd(kernel_params, local_host)
        return self.output_static(kernel_params, path)

    def compose_preseed_url(self, url):
        """Modifies the url to replace all forward slashes with
        backslashes, and prepends the ^ character to any upper-case
        characters.

        Boot load options of Windows will all be upper-cased
        as Windows does not care about case, and what gets exposed in the
        registry is all uppercase. MAAS requires a case-sensitive url.

        The Windows install script extracts the preseed url and any character
        that starts with ^ is then uppercased, so that the URL is correct.
        """
        url = url.replace("/", "\\")
        return re.sub(r"([A-Z])", r"^\1", url)

    def get_resource_path(self, kernel_params, path):
        """Gets the resource path from the kernel param."""
        with ClusterConfiguration.open() as config:
            resources = config.tftp_root
        return os.path.join(
            resources,
            "windows",
            kernel_params.arch,
            kernel_params.subarch,
            kernel_params.release,
            kernel_params.label,
            path,
        )

    def compose_bcd(self, kernel_params, local_host):
        """Composes the Windows boot configuration data.

        :param kernel_params: An instance of `KernelParameters`.
        :return: Binary data
        """
        preseed_url = self.compose_preseed_url(kernel_params.preseed_url)
        release_path = "%s\\source" % kernel_params.release
        remote_path = "\\\\%s\\reminst" % local_host
        loadoptions = f"{remote_path};{release_path};{preseed_url}"

        # Generate the bcd file.
        bcd_template = self.get_resource_path(kernel_params, "bcd")
        if not os.path.isfile(bcd_template):
            raise BootMethodError(
                "Failed to find bcd template: %s" % bcd_template
            )
        with tempdir() as tmp:
            bcd_tmp = os.path.join(tmp, "bcd")
            shutil.copyfile(bcd_template, bcd_tmp)

            bcd = Bcd(bcd_tmp)
            bcd.set_load_options(loadoptions)

            with open(bcd_tmp, "rb") as stream:
                return BytesReader(stream.read())

    def output_static(self, kernel_params, path):
        """Outputs the static file based on the version of Windows."""
        actual_path = self.get_resource_path(kernel_params, path)
        return FilesystemReader(FilePath(actual_path))

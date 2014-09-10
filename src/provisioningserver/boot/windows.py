# Copyright 2014 Cloudbase Solutions SRL.
# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Windows PXE Boot Method"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'WindowsPXEBootMethod',
    ]

import json
import os.path
import re
import shutil
import sys

from provisioningserver.boot import (
    BootMethod,
    BootMethodError,
    BytesReader,
    get_remote_mac,
    )
from provisioningserver.cluster_config import get_cluster_uuid
from provisioningserver.config import Config
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.twisted import deferred
from tftp.backend import FilesystemReader
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.python.context import get
from twisted.python.filepath import FilePath

# These files do not exist in the tftproot. WindowsPXEBootMethod
# handles access to these files returning the correct version
# of the file for the booting version of Windows.
#
# Note: Each version of Windows can have different content for
# these files.
STATIC_FILES = [
    'pxeboot.0',
    'bootmgr.exe',
    '\\boot\\bcd',
    '\\boot\\winpe.wim',
    '\\boot\\boot.sdi',
    '\\boot\\font\\wgl4_boot.ttf',
    ]


def get_hivex_module():
    """Returns the hivex module if avaliable.

    python-hivex is an optional dependency, but it is needed
    before MAAS can boot Windows.
    """
    if 'hivex' not in sys.modules:
        try:
            __import__('hivex')
        except ImportError:
            return None
    return sys.modules['hivex']


def load_hivex(*args, **kwargs):
    """Returns the Hivex object."""
    module = get_hivex_module()
    if module is None:
        return None
    return module.Hivex(*args, **kwargs)


class Bcd:
    """Allows modification of the load options in a Windows boot
    configuration data file.

    References:
        http://msdn.microsoft.com/en-us/library/windows/desktop/
            - aa362652(v=vs.85).aspx
            - aa362641(v=vs.85).aspx
    """

    GUID_WINDOWS_BOOTMGR = '{9dea862c-5cdd-4e70-acc1-f32b344d4795}'
    BOOT_MGR_DISPLAY_ORDER = '24000001'
    LOAD_OPTIONS = '12000030'

    def __init__(self, filename):
        self.hive = load_hivex(filename, write=True)

        # uids
        objects = self._get_root_objects()
        self.uids = {}
        for i in self.hive.node_children(objects):
            self.uids[self.hive.node_name(i)] = self.hive.node_children(i)

        # default bootloader
        mgr = self.uids[self.GUID_WINDOWS_BOOTMGR][1]
        bootmgr_elems = dict([(self.hive.node_name(i), i) for i in
                             self.hive.node_children(mgr)])
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
        return elems['Objects']

    def _get_loader(self, bootmgr_elems):
        """Get default bootloader."""
        (val,) = self.hive.node_values(
            bootmgr_elems[self.BOOT_MGR_DISPLAY_ORDER])
        loader = self.hive.value_multiple_strings(val)[0]
        return loader

    def _get_loader_elems(self):
        """Get elements present in default boot loader. We need this
        in order to determine the loadoptions key.
        """
        return dict(
            [(self.hive.node_name(i), i)
                for i in self.hive.node_children(self.uids[self.loader][1])])

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
                self.uids[self.loader][1], self.LOAD_OPTIONS)
        k_type = 1
        key = "Element"
        data = {
            't': k_type,
            'key': key,
            # Windows only accepts utf-16le in load options.
            'value': value.decode('utf-8').encode('utf-16le'),
            }
        self.hive.node_set_value(h, data)
        self.hive.commit(None)


class WindowsPXEBootMethod(BootMethod):

    name = "windows"
    template_subdir = "windows"
    bootloader_path = "pxeboot.0"
    arch_octet = None

    @deferred
    def get_node_info(self, backend):
        """Gets node information from the backend."""
        local_host, local_port = get("local", (None, None))
        remote_host, remote_port = get("remote", (None, None))

        remote_mac = get_remote_mac()
        params = {
            "local": local_host,
            "remote": remote_host,
            "mac": remote_mac,
            "cluster_uuid": get_cluster_uuid(),
            }

        url = backend.get_generator_url(params)

        def set_remote_mac(data):
            if data is not None:
                data['mac'] = remote_mac
            return data

        d = backend.get_page(url)
        d.addCallback(json.loads)
        d.addCallback(set_remote_mac)
        return d

    def clean_path(self, path):
        """Converts Windows path into a unix path and strips the
        boot subdirectory from the paths.
        """
        path = path.lower().replace('\\', '/')
        if path[0:6] == "/boot/":
            path = path[6:]
        return path

    @inlineCallbacks
    def match_path(self, backend, path):
        """Checks path to see if the boot method should handle
        the requested file.

        :param backend: requesting backend
        :param path: requested path
        :returns: dict of match params from path, None if no match
        """
        # If the node is requesting the initial bootloader, then we
        # need to see if this node is set to boot Windows first.
        local_host, local_port = get("local", (None, None))
        if path == 'pxelinux.0':
            data = yield self.get_node_info(backend)
            if data is None:
                returnValue(None)

            # Only provide the Windows bootloader when installing
            # PXELINUX chainloading will work for the rest of the time.
            purpose = data.get('purpose')
            if purpose != 'install':
                returnValue(None)

            osystem = data.get('osystem')
            if osystem == 'windows':
                # python-hivex is needed to continue.
                if get_hivex_module() is None:
                    raise BootMethodError('python-hivex package is missing.')

                returnValue({
                    'mac': data.get('mac'),
                    'path': self.bootloader_path,
                    'local_host': local_host,
                    })
        # Fix the paths for the other static files, Windows requests.
        elif path.lower() in STATIC_FILES:
            returnValue({
                'mac': get_remote_mac(),
                'path': self.clean_path(path),
                'local_host': local_host,
                })
        returnValue(None)

    def get_reader(self, backend, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """
        path = extra['path']
        if path == 'bcd':
            local_host = extra['local_host']
            return self.compose_bcd(kernel_params, local_host)
        return self.output_static(kernel_params, path)

    def install_bootloader(self, destination):
        """Installs the required files for Windows booting into the
        tftproot.

        Does nothing. Windows requires manual installation of bootloader
        files, due to licensing.
        """

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
        url = url.replace('/', '\\')
        return re.sub(r"([A-Z])", r"^\1", url)

    def get_resource_path(self, kernel_params, path):
        """Gets the resource path from the kernel param."""
        resources = Config.load_from_cache()['tftp']['resource_root']
        return os.path.join(
            resources, 'windows', kernel_params.arch, kernel_params.subarch,
            kernel_params.release, kernel_params.label, path)

    def compose_bcd(self, kernel_params, local_host):
        """Composes the Windows boot configuration data.

        :param kernel_params: An instance of `KernelParameters`.
        :returns: Binary data
        """
        preseed_url = self.compose_preseed_url(kernel_params.preseed_url)
        release_path = "%s\\source" % kernel_params.release
        remote_path = "\\\\%s\\reminst" % local_host
        loadoptions = "%s;%s;%s" % \
            (remote_path, release_path, preseed_url)

        # Generate the bcd file.
        bcd_template = self.get_resource_path(kernel_params, "bcd")
        if not os.path.isfile(bcd_template):
            raise BootMethodError(
                "Failed to find bcd template: %s" % bcd_template)
        with tempdir() as tmp:
            bcd_tmp = os.path.join(tmp, "bcd")
            shutil.copyfile(bcd_template, bcd_tmp)

            bcd = Bcd(bcd_tmp)
            bcd.set_load_options(loadoptions)

            with open(bcd_tmp, 'rb') as stream:
                return BytesReader(stream.read())

    def output_static(self, kernel_params, path):
        """Outputs the static file based on the version of Windows."""
        actual_path = self.get_resource_path(kernel_params, path)
        return FilesystemReader(FilePath(actual_path))

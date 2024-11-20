# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""S390X DPM Partition Boot Method"""


import tempita

from maascommon.bootmethods import S390XPartitionBootMetadata
from provisioningserver.boot import BootMethod, BytesReader, get_remote_mac
from provisioningserver.boot.s390x import format_bootif
from provisioningserver.kernel_opts import compose_kernel_command_line


class S390XPartitionBootMethod(BootMethod, S390XPartitionBootMetadata):
    def match_path(self, backend, path):
        """Checks path for the configuration file that needs to be
        generated.

        :param backend: requesting backend
        :param path: requested path
        :return: dict of match params from path, None if no match
        """
        if path == self.bootloader_path.encode():
            return {
                "arch": "s390x",
                "mac": get_remote_mac(),
            }
        else:
            return None

    def get_reader(self, backend, kernel_params, mac=None, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param mac: Optional MAC address discovered by `match_path`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """
        template = self.get_template(
            kernel_params.purpose, kernel_params.arch, kernel_params.subarch
        )
        namespace = self.compose_template_namespace(kernel_params)

        def kernel_command(params):
            cmd_line = compose_kernel_command_line(params)
            # Modify the kernel_command to inject the BOOTIF. S390X doesn't
            # support the IPAPPEND pxelinux flag.
            if mac is not None:
                return f"{cmd_line} BOOTIF={format_bootif(mac)}"
            return cmd_line

        namespace["kernel_command"] = kernel_command

        # We are going to do 2 passes of tempita substitution because there
        # may be things like kernel params which include variables that can
        # only be populated at run time and thus contain variables themselves.
        # For example, an OS may need a kernel parameter that points back to
        # fs_host and the kernel parameter comes through as part of the simple
        # stream.
        step1 = template.substitute(namespace)
        return BytesReader(
            tempita.Template(step1).substitute(namespace).encode("utf-8")
        )

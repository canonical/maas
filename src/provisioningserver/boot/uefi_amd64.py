# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""UEFI AMD64 Boot Method"""


from itertools import repeat
import os
import re
from textwrap import dedent

from provisioningserver.boot import BootMethod, BytesReader, get_parameters
from provisioningserver.events import EVENT_TYPES, try_send_rack_event
from provisioningserver.kernel_opts import compose_kernel_command_line
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import typed
from provisioningserver.utils.fs import atomic_symlink

maaslog = get_maas_logger("uefi_amd64")


CONFIG_FILE = dedent(
    """
    # MAAS GRUB2 pre-loader configuration file

    # Load based on MAC address first.
    configfile (pxe)/grub/grub.cfg-${net_default_mac}

    # Failed to load based on MAC address.
    # Load amd64 by default, UEFI only supported by 64-bit
    configfile (pxe)/grub/grub.cfg-default-amd64
    """
)

# GRUB EFINET represents a MAC address in IEEE 802 colon-seperated
# format. Required for UEFI as GRUB2 only presents the MAC address
# in colon-seperated format.
re_mac_address_octet = r"[0-9a-f]{2}"
re_mac_address = re.compile(":".join(repeat(re_mac_address_octet, 6)))

# Match the grub/grub.cfg-* request for UEFI (aka. GRUB2)
re_config_file = r"""
    # Optional leading slash(es).
    ^/*
    grub/grub[.]cfg   # UEFI (aka. GRUB2) expects this.
    -
    (?: # either a MAC
        (?P<mac>{re_mac_address.pattern}) # Capture UEFI MAC.
    | # or "default"
        default
          (?: # perhaps with specified arch, with a separator of '-'
            [-](?P<arch>\w+) # arch
            (?:-(?P<subarch>\w+))? # optional subarch
          )?
    )
    $
"""

re_config_file = re_config_file.format(re_mac_address=re_mac_address)
re_config_file = re_config_file.encode("ascii")
re_config_file = re.compile(re_config_file, re.VERBOSE)


class UEFIAMD64BootMethod(BootMethod):

    name = "uefi_amd64"
    bios_boot_method = "uefi"
    template_subdir = "uefi"
    bootloader_arches = ["amd64"]
    bootloader_path = "bootx64.efi"
    bootloader_files = ["bootx64.efi", "grubx64.efi"]
    arch_octet = ["00:07", "00:09"]
    user_class = None

    def match_path(self, backend, path):
        """Checks path for the configuration file that needs to be
        generated.

        :param backend: requesting backend
        :param path: requested path
        :return: dict of match params from path, None if no match
        """
        match = re_config_file.match(path)
        if match is None:
            return None
        params = get_parameters(match)

        # MAC address is in the wrong format, fix it
        mac = params.get("mac")
        if mac is not None:
            params["mac"] = mac.replace(":", "-")

        return params

    def get_reader(self, backend, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """

        def kernel_command(params):
            """Return the kernel command, adjusted for UEFI to work.

            See the similar function in BootMethod, and the callsite below.

            The issue here is that grub throws a fit when the braces on
            cc:{...}end_cc are hit, for whatever reason.  Escape _JUST_ those.
            """
            return re.sub(
                r"cc:{(?P<inner>[^}]*)}end_cc",
                r"cc:\{\g<inner>\}end_cc",
                compose_kernel_command_line(params),
            )

        template = self.get_template(
            kernel_params.purpose, kernel_params.arch, kernel_params.subarch
        )
        namespace = self.compose_template_namespace(kernel_params)
        # Bug#1651452 - kernel command needs some extra escapes, but ONLY for
        # UEFI.  And so we fix it here, instead of in the common code.  See
        # also src/provisioningserver/kernel_opts.py.
        namespace["kernel_command"] = kernel_command
        return BytesReader(
            template.substitute(namespace).strip().encode("utf-8")
        )

    def _find_and_copy_bootloaders(self, destination, log_missing=True):
        if not super()._find_and_copy_bootloaders(destination, False):
            # If a previous copy of the UEFI AMD64 Grub files can't be found
            # see the files are on the system from an Ubuntu package install.
            # The package uses a different filename than what MAAS uses so
            # when we copy make sure the right name is used.
            missing_files = []

            if os.path.exists("/usr/lib/shim/shim.efi.signed"):
                atomic_symlink(
                    "/usr/lib/shim/shim.efi.signed",
                    os.path.join(destination, "bootx64.efi"),
                )
            else:
                missing_files.append("bootx64.efi")

            if os.path.exists(
                "/usr/lib/grub/x86_64-efi-signed/grubnetx64.efi.signed"
            ):
                atomic_symlink(
                    "/usr/lib/grub/x86_64-efi-signed/grubnetx64.efi.signed",
                    os.path.join(destination, "grubx64.efi"),
                )
            else:
                missing_files.append("grubx64.efi")

            if missing_files != [] and log_missing:
                err_msg = (
                    "Unable to find a copy of %s in the SimpleStream and the "
                    "packages shim-signed, and grub-efi-amd64-signed are not "
                    "installed. The %s bootloader type may not work."
                    % (", ".join(missing_files), self.name)
                )
                try_send_rack_event(EVENT_TYPES.RACK_IMPORT_ERROR, err_msg)
                maaslog.error(err_msg)
                return False
        return True

    @typed
    def link_bootloader(self, destination: str):
        super().link_bootloader(destination)
        config_path = os.path.join(destination, "grub")
        config_dst = os.path.join(config_path, "grub.cfg")
        if not os.path.exists(config_path):
            os.makedirs(config_path)
        with open(config_dst, "wb") as stream:
            stream.write(CONFIG_FILE.encode("utf-8"))


class UEFIAMD64HTTPBootMethod(UEFIAMD64BootMethod):

    name = "uefi_amd64_http"
    bios_boot_method = "uefi"
    template_subdir = "uefi"
    bootloader_path = "bootx64.efi"
    bootloader_arches = []  # `UEFIAMD64BootMethod` provides this.
    bootloader_files = []  # `UEFIAMD64BootMethod` provides this.
    arch_octet = ["00:0f", "00:10"]
    user_class = None
    absolute_url_as_filename = True
    http_url = True

    def match_path(self, backend, path):
        # Does nothing as `UEFIAMD64BootMethod` provides this.
        return None

    def get_reader(self, backend, kernel_params, **extra):
        # Does nothing as `UEFIAMD64BootMethod` provides this.
        return None

    @typed
    def link_bootloader(self, destination: str):
        # Does nothing as `UEFIAMD64BootMethod` provides this.
        return None

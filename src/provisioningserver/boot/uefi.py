# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""UEFI Boot Method"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'UEFIBootMethod',
    ]

from itertools import repeat
import os.path
import re
from textwrap import dedent
import urllib2
from urlparse import urljoin

from provisioningserver.boot import (
    BootMethod,
    BootMethodInstallError,
    BytesReader,
    get_parameters,
    utils,
    )
from provisioningserver.boot.install_bootloader import (
    install_bootloader,
    make_destination,
    )
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.region import GetArchiveMirrors
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.shell import call_and_check
from provisioningserver.utils.twisted import asynchronous
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )


ARCHIVE_PATH = "/main/uefi/grub2-amd64/current/grubnetx64.efi.signed"

CONFIG_FILE = dedent("""
    # MAAS GRUB2 pre-loader configuration file

    # Load based on MAC address first.
    configfile (pxe)/grub/grub.cfg-${net_default_mac}

    # Failed to load based on MAC address.
    # Load amd64 by default, UEFI only supported by 64-bit
    configfile (pxe)/grub/grub.cfg-default-amd64
    """)

# GRUB EFINET represents a MAC address in IEEE 802 colon-seperated
# format. Required for UEFI as GRUB2 only presents the MAC address
# in colon-seperated format.
re_mac_address_octet = r'[0-9a-f]{2}'
re_mac_address = re.compile(
    ':'.join(repeat(re_mac_address_octet, 6)))

# Match the grub/grub.cfg-* request for UEFI (aka. GRUB2)
re_config_file = r'''
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
'''

re_config_file = re_config_file.format(
    re_mac_address=re_mac_address)
re_config_file = re.compile(re_config_file, re.VERBOSE)


@asynchronous
def get_archive_mirrors():
    client = getRegionClient()
    return client(GetArchiveMirrors)


@asynchronous(timeout=10)
@inlineCallbacks
def get_main_archive_url():
    mirrors = yield get_archive_mirrors()
    main_url = mirrors['main'].geturl()
    returnValue(main_url)


def archive_grubnet_urls(main_url):
    """Paths to try to download grubnetx64.efi.signed."""
    release = utils.get_distro_release()
    # grubnetx64 will not work below version trusty, as efinet is broken
    # when loading kernel, force trusty. Note: This is only the grub version
    # this should not block any of the previous release from running.
    if release in ['lucid', 'precise', 'quantal', 'saucy']:
        release = 'trusty'
    if not main_url.endswith('/'):
        main_url = main_url + '/'
    dists_url = urljoin(main_url, 'dists')
    for dist in ['%s-updates' % release, release]:
        yield "%s/%s/%s" % (
            dists_url.rstrip("/"),
            dist,
            ARCHIVE_PATH.rstrip("/"))


def download_grubnet(main_url, destination):
    """Downloads grubnetx64.efi.signed from the archive."""
    for url in archive_grubnet_urls(main_url):
        try:
            response = urllib2.urlopen(url)
        # Okay, if it fails as the updates area might not hold
        # that file.
        except urllib2.URLError:
            continue

        with open(destination, 'wb') as stream:
            stream.write(response.read())
        return True
    return False


class UEFIBootMethod(BootMethod):

    name = "uefi"
    template_subdir = "uefi"
    bootloader_arches = ['amd64']
    bootloader_path = "bootx64.efi"
    arch_octet = "00:07"  # AMD64 EFI

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
            params["mac"] = mac.replace(':', '-')

        return params

    def get_reader(self, backend, kernel_params, **extra):
        """Render a configuration file as a unicode string.

        :param backend: requesting backend
        :param kernel_params: An instance of `KernelParameters`.
        :param extra: Allow for other arguments. This is a safety valve;
            parameters generated in another component (for example, see
            `TFTPBackend.get_boot_method_reader`) won't cause this to break.
        """
        template = self.get_template(
            kernel_params.purpose, kernel_params.arch,
            kernel_params.subarch)
        namespace = self.compose_template_namespace(kernel_params)
        return BytesReader(template.substitute(namespace).encode("utf-8"))

    def install_bootloader(self, destination):
        """Installs the required files for UEFI booting into the
        tftproot.
        """
        archive_url = get_main_archive_url()
        with tempdir() as tmp:
            # Download the shim-signed package
            data, filename = utils.get_updates_package(
                'shim-signed', archive_url,
                'main', 'amd64')
            if data is None:
                raise BootMethodInstallError(
                    'Failed to download shim-signed package from '
                    'the archive.')
            shim_output = os.path.join(tmp, filename)
            with open(shim_output, 'wb') as stream:
                stream.write(data)

            # Extract the package with dpkg, and install the shim
            call_and_check(["dpkg", "-x", shim_output, tmp])
            install_bootloader(
                os.path.join(tmp, 'usr', 'lib', 'shim', 'shim.efi.signed'),
                os.path.join(destination, self.bootloader_path))

            # Download grubnetx64 from the archive and install
            grub_tmp = os.path.join(tmp, 'grubnetx64.efi.signed')
            if download_grubnet(archive_url, grub_tmp) is False:
                raise BootMethodInstallError(
                    'Failed to download grubnetx64.efi.signed '
                    'from the archive.')
            grub_dst = os.path.join(destination, 'grubx64.efi')
            install_bootloader(grub_tmp, grub_dst)

        config_path = os.path.join(destination, 'grub')
        config_dst = os.path.join(config_path, 'grub.cfg')
        make_destination(config_path)
        with open(config_dst, 'wb') as stream:
            stream.write(CONFIG_FILE.encode("utf-8"))

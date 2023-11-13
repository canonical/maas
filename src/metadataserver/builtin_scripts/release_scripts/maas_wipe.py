#!/usr/bin/env python3
#
# wipe-disks - Wipe disks content.
#
# Copyright (C) 2016-2023 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# --- Start MAAS 1.0 script metadata ---
# name: wipe-disks
# title: Wipe disks content
# description: Wipe disks content, optionally with quick or secure erase
# tags: wipe, disk, storage
# script_type: release
# parameters:
#   quick_erase:
#     type: boolean
#     argument_format: --quick-erase
#   secure_erase:
#     type: boolean
#     argument_format: --secure-erase
# packages:
#   apt:
#     - nvme-cli
# --- End MAAS 1.0 script metadata --

import mmap
import os
import re
import subprocess

# Path to dev. Used for testing this script.
DEV_PATH = b"/dev/%s"


class WipeError(Exception):
    """Raised when wiping has failed."""


def print_flush(*args, **kwargs):
    kwargs["flush"] = True
    print(*args, **kwargs)


def list_disks():
    """Return list of disks to wipe."""
    disks = []
    output = subprocess.check_output(["lsblk", "-d", "-n", "-oKNAME,TYPE,RO"])
    for line in output.splitlines():
        kname, blk_type, readonly = line.split()
        if blk_type == b"disk" and readonly == b"0":
            disks.append(kname)
    return disks


def get_nvme_security_info(disk):
    """Gather NVMe information from the NVMe disks using the
    nvme-cli tool. Info from id-ctrl and id-ns is needed for
    secure erase (nvme format) and write zeroes."""

    # Grab the relevant info from nvme id-ctrl. We need to check the
    # following bits:
    #
    # OACS (Optional Admin Command Support) bit 1: Format supported
    # ONCS (Optional NVM Command Support) bit 3: Write Zeroes supported
    # FNA (Format NVM Attributes) bit 2: Cryptographic format supported

    security_info = {
        "format_supported": False,
        "writez_supported": False,
        "crypto_format": False,
        "nsze": 0,
        "lbaf": 0,
        "ms": 0,
    }

    try:
        output = subprocess.check_output(["nvme", "id-ctrl", DEV_PATH % disk])
    except subprocess.CalledProcessError as exc:
        print_flush("Error on nvme id-ctrl (%s)" % exc.returncode)
        return security_info
    except OSError as exc:
        print_flush("OS error when running nvme-cli (%s)" % exc.strerror)
        return security_info

    output = output.decode()

    for line in output.split("\n"):
        if "oacs" in line:
            oacs = line.split(":")[1]
            if int(oacs, 16) & 0x2:
                security_info["format_supported"] = True

        if "oncs" in line:
            oncs = line.split(":")[1]
            if int(oncs, 16) & 0x8:
                security_info["writez_supported"] = True

        if "fna" in line:
            fna = line.split(":")[1]
            if int(fna, 16) & 0x4:
                security_info["crypto_format"] = True

    # Next step: collect LBAF (LBA Format), MS (Metadata Setting) and
    # NSZE (Namespace Size) from id-ns. According to NVMe spec, bits 0:3
    # from FLBAS corresponds to the LBAF value, whereas bit 4 is MS.

    try:
        output = subprocess.check_output(["nvme", "id-ns", DEV_PATH % disk])
    except subprocess.CalledProcessError as exc:
        print_flush("Error on nvme id-ns (%s)" % exc.returncode)
        security_info["format_supported"] = False
        security_info["writez_supported"] = False
        return security_info
    except OSError as exc:
        print_flush("OS error when running nvme-cli (%s)" % exc.strerror)
        security_info["format_supported"] = False
        security_info["writez_supported"] = False
        return security_info

    output = output.decode()

    for line in output.split("\n"):
        if "nsze" in line:
            # According to spec., this should be used as 0-based value.
            nsze = line.split(":")[1]
            security_info["nsze"] = int(nsze, 16) - 1

        if "flbas" in line:
            flbas = line.split(":")[1]
            flbas = int(flbas, 16)
            security_info["lbaf"] = flbas & 0xF

            if flbas & 0x10:
                security_info["ms"] = 1

    return security_info


def get_hdparm_security_info(disk):
    """Get SCSI/ATA disk security info from hdparm.
    Sadly hdparam doesn't provide an output that makes it easy to parse.
    """

    # Grab the security section for hdparam.
    security_section = []
    output = subprocess.check_output([b"hdparm", b"-I", DEV_PATH % disk])
    match = re.search(
        rb"Security:\s*$(.*?)\s*^Logical Unit",
        output,
        re.DOTALL | re.MULTILINE,
    )
    security_section = b"" if match is None else match.group(1)

    # Determine if security is supported, enabled, locked, or frozen.
    security_info = {
        b"supported": False,
        b"enabled": False,
        b"locked": False,
        b"frozen": False,
    }
    matches = re.findall(
        rb"^\s*(?:(not)\s+)?(supported|enabled|frozen|locked)$",
        security_section,
        re.MULTILINE,
    )
    for modifier, feature in matches:
        security_info[feature] = len(modifier) == 0
    return security_info


def get_disk_security_info(disk):
    """Get the disk security information.

    Uses `hdparam` to get security information about the SCSI/ATA disks.
    If NVMe, nvme-cli is used instead.
    """

    if b"nvme" in disk:
        return get_nvme_security_info(disk)

    return get_hdparm_security_info(disk)


def get_disk_info():
    """Return dictionary of wipeable disks and thier security information."""
    return {kname: get_disk_security_info(kname) for kname in list_disks()}


def secure_erase_hdparm(kname):
    """Securely wipe the device."""
    # First write 1 MiB of known data to the beginning of the block device.
    # This is used to check at the end of the secure erase that it worked
    # as expected. Notice that we use here direct R/W, in order to bypass Linux
    # page cache; or else we may fail the test (due to reading from page cache
    # instead of the just-erased disk). See LP #1900623.
    buf = b"M" * 1024 * 1024
    wmap = mmap.mmap(-1, 1024 * 1024)
    wmap.write(buf)

    wfd = os.open(DEV_PATH % kname, os.O_WRONLY | os.O_SYNC | os.O_DIRECT)
    os.write(wfd, wmap)
    os.close(wfd)
    wmap.close()

    # Before secure erase can be performed on a device a user password must
    # be set. The password will automatically be removed once the drive has
    # been securely erased.
    print_flush("%s: performing secure erase process." % kname.decode("ascii"))
    print_flush("%s: setting user password to 'maas'." % kname.decode("ascii"))
    try:
        subprocess.check_output(
            [
                b"hdparm",
                b"--user-master",
                b"u",
                b"--security-set-pass",
                b"maas",
                DEV_PATH % kname,
            ]
        )
    except Exception as exc:
        raise WipeError("Failed to set user password.") from exc

    # Now that the user password is set the device should have its
    # security mode enabled.
    info = get_hdparm_security_info(kname)
    if not info[b"enabled"]:
        # If not enabled that means the password did not take, so it does not
        # need to be cleared.
        raise WipeError("Failed to enable security to perform secure erase.")

    # Perform the actual secure erase. This will clear the set user password.
    failed_exc = None
    print_flush("%s: calling secure erase on device." % kname.decode("ascii"))
    try:
        subprocess.check_call(
            [
                b"hdparm",
                b"--user-master",
                b"u",
                b"--security-erase",
                b"maas",
                DEV_PATH % kname,
            ]
        )
    except Exception as exc:
        # Secure erase has failed. Set the exception that was raised.
        failed_exc = exc

    # Make sure that the device is now not enabled.
    info = get_hdparm_security_info(kname)
    if info[b"enabled"]:
        # Wipe failed since security is still enabled.
        subprocess.check_output(
            [b"hdparm", b"--security-disable", b"maas", DEV_PATH % kname]
        )
        raise WipeError("Failed to securely erase.") from failed_exc

    # Check that the initial part of the disk is not the same. Again, we rely
    # on direct I/O here, to bypass the page cache (LP #1900623).
    rfd = os.open(DEV_PATH % kname, os.O_RDONLY | os.O_SYNC | os.O_DIRECT)
    fobj = os.fdopen(rfd, "rb")
    rmap = mmap.mmap(-1, 1024 * 1024)
    fobj.readinto(rmap)

    read_buf = rmap.read(len(buf))
    fobj.close()
    rmap.close()

    if read_buf == buf:
        raise WipeError(
            "Secure erase was performed, but failed to actually work."
        )


def try_secure_erase_hdparm(kname, info):
    """Try to wipe the disk with secure erase."""
    if info[b"supported"]:
        if info[b"frozen"]:
            print_flush(
                "%s: not using secure erase; "
                "drive is currently frozen." % kname.decode("ascii")
            )
            return False
        elif info[b"locked"]:
            print_flush(
                "%s: not using secure erase; "
                "drive is currently locked." % kname.decode("ascii")
            )
            return False
        elif info[b"enabled"]:
            print_flush(
                "%s: not using secure erase; "
                "drive security is already enabled." % kname.decode("ascii")
            )
            return False
        else:
            # Wiping using secure erase.
            try:
                secure_erase_hdparm(kname)
            except Exception as e:
                print_flush(
                    "%s: failed to be securely erased: %s"
                    % (kname.decode("ascii"), e)
                )
                return False
            else:
                print_flush(
                    "%s: successfully securely erased."
                    % (kname.decode("ascii"))
                )
                return True
    else:
        print_flush(
            "%s: drive does not support secure erase."
            % (kname.decode("ascii"))
        )
        return False


def try_secure_erase_nvme(kname, info):
    """Perform a secure-erase on NVMe disk if that feature is
    available. Prefer cryptographic erase, when available."""

    if not info["format_supported"]:
        print_flush(
            "Device %s does not support formatting" % kname.decode("ascii")
        )
        return False

    if info["crypto_format"]:
        ses = 2
    else:
        ses = 1

    try:
        subprocess.check_output(
            [
                "nvme",
                "format",
                "-s",
                str(ses),
                "-l",
                str(info["lbaf"]),
                "-m",
                str(info["ms"]),
                DEV_PATH % kname,
            ]
        )
    except subprocess.CalledProcessError as exc:
        print_flush("Error with format command (%s)" % exc.returncode)
        return False
    except OSError as exc:
        print_flush("OS error when running nvme-cli (%s)" % exc.strerror)
        return False

    print_flush(
        "Secure erase was successful on NVMe drive %s" % kname.decode("ascii")
    )
    return True


def try_secure_erase(kname, info):
    """Entry-point for secure-erase for SCSI/ATA or NVMe disks."""

    if b"nvme" in kname:
        return try_secure_erase_nvme(kname, info)

    return try_secure_erase_hdparm(kname, info)


def wipe_quickly(kname):
    """Quickly wipe the disk by using wipefs and zeroing the beginning
    and end of the disk. This is not a secure erase but does make it
    harder to get the data from the device and also clears previous layouts.
    """

    wipe_error = 0
    print_flush("%s: starting quick wipe." % kname.decode("ascii"))
    try:
        subprocess.check_output(["wipefs", "-f", "-a", DEV_PATH % kname])
        wipe_error -= 1
    except subprocess.CalledProcessError as exc:
        print_flush(
            "{}: wipefs failed ({})".format(
                kname.decode("ascii"), exc.returncode
            )
        )
        wipe_error += 1

    buf = b"\0" * 1024 * 1024 * 2  # 2 MiB
    try:
        fp = open(DEV_PATH % kname, "wb")
        fp.write(buf)
        fp.seek(-len(buf), 2)
        fp.write(buf)
        wipe_error -= 1
    except OSError as exc:
        print_flush(
            "%s: OS error while wiping beginning/end of disk (%s)"
            % (kname.decode("ascii"), exc.strerror)
        )
        wipe_error += 1

    if wipe_error > 0:
        print_flush("%s: failed to be quickly wiped." % kname.decode("ascii"))
    else:
        print_flush("%s: successfully quickly wiped." % kname.decode("ascii"))


def nvme_write_zeroes(kname, info):
    """Perform a write-zeroes operation on NVMe device instead of
    dd'ing 0 to the entire disk if secure erase is not available.
    Write-zeroes is a faster way to clean a NVMe disk."""

    fallback = False

    if not info["writez_supported"]:
        print(
            "NVMe drive %s does not support write-zeroes"
            % kname.decode("ascii")
        )
        fallback = True

    if info["nsze"] <= 0:
        print(
            "Bad namespace information collected on NVMe drive %s"
            % kname.decode("ascii")
        )
        fallback = True

    if fallback:
        print_flush("Will fallback to regular drive zeroing.")
        return False

    try:
        subprocess.check_output(
            [
                "nvme",
                "write-zeroes",
                "-f",
                "-s",
                "0",
                "-c",
                str(hex(info["nsze"])[2:]),
                DEV_PATH % kname,
            ]
        )
    except subprocess.CalledProcessError as exc:
        print_flush("Error with write-zeroes command (%s)" % exc.returncode)
        return False
    except OSError as exc:
        print_flush("OS error when running nvme-cli (%s)" % exc.strerror)
        return False

    print_flush(
        "%s: successfully zeroed (using write-zeroes)." % kname.decode("ascii")
    )
    return True


def zero_disk(kname, info):
    """Zero the entire disk, trying write-zeroes first if NVMe disk."""

    if b"nvme" in kname:
        if nvme_write_zeroes(kname, info):
            return

    # Get the total size of the device.
    size = 0
    with open(DEV_PATH % kname, "rb") as fp:
        fp.seek(0, 2)
        size = fp.tell()

    print_flush("%s: started zeroing." % kname.decode("ascii"))

    # Write 1MiB at a time.
    buf = b"\0" * 1024 * 1024
    count = size // len(buf)
    with open(DEV_PATH % kname, "wb") as fp:
        for _ in range(count):
            fp.write(buf)

        # If the size of the disk is not divisable by 1 MiB, write the
        # remaining part of the disk.
        remaining = size - (count * len(buf))
        if remaining > 0:
            buf = b"\0" * remaining
            fp.write(buf)

    print_flush("%s: successfully zeroed." % kname.decode("ascii"))


def main():
    # Parse available arguments.
    import argparse
    import textwrap

    parser = argparse.ArgumentParser(
        description="Wipes all disks.",
        epilog=textwrap.dedent(
            """\
            If neither --secure-erase nor --quick-erase are specified,
            wipe-disks will overwrite the whole disk with null bytes. This
            can be very slow.

            If both --secure-erase and --quick-erase are specified and the
            drive does NOT have a secure erase feature, wipe-disks will
            behave as if only --quick-erase was specified.

            If --secure-erase is specified and --quick-erase is NOT specified
            and the drive does NOT have a secure erase feature, wipe-disks
            will behave as if --secure-erase was NOT specified, i.e. will
            overwrite the whole disk with null bytes. This can be very slow.
            """
        ),
    )
    parser.add_argument(
        "--secure-erase",
        action="store_true",
        default=False,
        help=(
            "Use the drive's secure erase feature if available. In some cases "
            "this can be much faster than overwriting the drive. Some drives "
            "implement secure erasure by overwriting themselves so this could "
            "still be slow."
        ),
    )
    parser.add_argument(
        "--quick-erase",
        action="store_true",
        default=False,
        help=(
            "Wipe 2MiB at the start and at the end of the drive to make data "
            "recovery inconvenient and unlikely to happen by accident. Also, "
            "it runs wipefs to clear known partition/layout signatures. This "
            "is not secure."
        ),
    )
    args = parser.parse_args()

    # Gather disk information.
    disk_info = get_disk_info()
    print_flush(
        "%s to be wiped." % (b", ".join(disk_info.keys())).decode("ascii")
    )

    # Wipe all disks.
    for kname, info in disk_info.items():
        wiped = False
        if args.secure_erase:
            wiped = try_secure_erase(kname, info)
        if not wiped:
            if args.quick_erase:
                wipe_quickly(kname)
            else:
                zero_disk(kname, info)

    print_flush("All disks have been successfully wiped.")


if __name__ == "__main__":
    main()

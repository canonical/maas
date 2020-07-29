#!/usr/bin/python3
# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

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


def get_disk_security_info(disk):
    """Get the disk security information.

    Uses `hdparam` to get security information about the disk. Sadly hdparam
    doesn't provide an output that makes it easy to parse.
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


def get_disk_info():
    """Return dictionary of wipeable disks and thier security information."""
    return {kname: get_disk_security_info(kname) for kname in list_disks()}


def try_secure_erase(kname, info):
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
                secure_erase(kname)
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


def secure_erase(kname):
    """Securely wipe the device."""
    # First write 1 MiB of known data to the beginning of the block device.
    # This is used to check at the end of the secure erase that it worked
    # as expected.
    buf = b"M" * 1024 * 1024
    with open(DEV_PATH % kname, "wb") as fp:
        fp.write(buf)

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
    info = get_disk_security_info(kname)
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
    info = get_disk_security_info(kname)
    if info[b"enabled"]:
        # Wipe failed since security is still enabled.
        subprocess.check_output(
            [b"hdparm", b"--security-disable", b"maas", DEV_PATH % kname]
        )
        raise WipeError("Failed to securely erase.") from failed_exc

    # Check that the initial part of the disk is not the same.
    with open(DEV_PATH % kname, "rb") as fp:
        read_buf = fp.read(len(buf))
    if read_buf == buf:
        raise WipeError(
            "Secure erase was performed, but failed to actually work."
        )


def wipe_quickly(kname):
    """Quickly wipe the disk by zeroing the beginning and end of the disk.

    This is not a secure erase but does make it harder to get the data from
    the device.
    """
    print_flush("%s: starting quick wipe." % kname.decode("ascii"))
    buf = b"\0" * 1024 * 1024 * 2  # 2 MiB
    with open(DEV_PATH % kname, "wb") as fp:
        fp.write(buf)
        fp.seek(-len(buf), 2)
        fp.write(buf)
    print_flush("%s: successfully quickly wiped." % kname.decode("ascii"))


def zero_disk(kname):
    """Zero the entire disk."""
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
            maas-wipe will overwrite the whole disk with null bytes. This
            can be very slow.

            If both --secure-erase and --quick-erase are specified and the
            drive does NOT have a secure erase feature, maas-wipe will
            behave as if only --quick-erase was specified.

            If --secure-erase is specified and --quick-erase is NOT specified
            and the drive does NOT have a secure erase feature, maas-wipe
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
            "Wipe 1MiB at the start and at the end of the drive to make data "
            "recovery inconvenient and unlikely to happen by accident. This "
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
                zero_disk(kname)

    print_flush("All disks have been successfully wiped.")


if __name__ == "__main__":
    main()

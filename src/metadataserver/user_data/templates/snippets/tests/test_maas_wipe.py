# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for maas_wipe.py."""

__all__ = []

import argparse
import subprocess
from textwrap import dedent
from unittest.mock import call, MagicMock

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from maastesting.testcase import MAASTestCase
from snippets import maas_wipe
from snippets.maas_wipe import (
    get_disk_info,
    get_disk_security_info,
    list_disks,
    secure_erase,
    try_secure_erase,
    wipe_quickly,
    WipeError,
    zero_disk,
)


HDPARM_BEFORE_SECURITY = b"""\
/dev/sda:

ATA device, with non-removable media
    Model Number:       INTEL SSDSC2CT240A4
    Serial Number:      CVKI3206029X240DGN
    Firmware Revision:  335u
    Transport:          Serial, ATA8-AST, SATA 1.0a, SATA II Extensions
Standards:
    Used: unknown (minor revision code 0xffff)
    Supported: 9 8 7 6 5
    Likely used: 9
Configuration:
    Logical		max	current
    cylinders	16383	16383
    heads		16	16
    sectors/track	63	63
    --
    CHS current addressable sectors:   16514064
    LBA    user addressable sectors:  268435455
    LBA48  user addressable sectors:  468862128
    Logical  Sector size:                   512 bytes
    Physical Sector size:                   512 bytes
    Logical Sector-0 offset:                  0 bytes
    device size with M = 1024*1024:      228936 MBytes
    device size with M = 1000*1000:      240057 MBytes (240 GB)
    cache/buffer size  = unknown
    Nominal Media Rotation Rate: Solid State Device
Capabilities:
    LBA, IORDY(can be disabled)
    Queue depth: 32
    Standby timer values: spec'd by Standard, no device specific minimum
    R/W multiple sector transfer: Max = 16	Current = 16
    Advanced power management level: 254
    DMA: mdma0 mdma1 mdma2 udma0 udma1 udma2 udma3 udma4 udma5 *udma6
         Cycle time: min=120ns recommended=120ns
    PIO: pio0 pio1 pio2 pio3 pio4
         Cycle time: no flow control=120ns  IORDY flow control=120ns
Commands/features:
    Enabled	Supported:
       *	SMART feature set
            Security Mode feature set
       *	Power Management feature set
       *	Write cache
       *	Look-ahead
       *	Host Protected Area feature set
       *	WRITE_BUFFER command
       *	READ_BUFFER command
       *	NOP cmd
       *	DOWNLOAD_MICROCODE
       *	Advanced Power Management feature set
            Power-Up In Standby feature set
       *	48-bit Address feature set
       *	Mandatory FLUSH_CACHE
       *	FLUSH_CACHE_EXT
       *	SMART error logging
       *	SMART self-test
       *	General Purpose Logging feature set
       *	WRITE_{DMA|MULTIPLE}_FUA_EXT
       *	64-bit World wide name
       *	IDLE_IMMEDIATE with UNLOAD
       *	WRITE_UNCORRECTABLE_EXT command
       *	{READ,WRITE}_DMA_EXT_GPL commands
       *	Segmented DOWNLOAD_MICROCODE
       *	Gen1 signaling speed (1.5Gb/s)
       *	Gen2 signaling speed (3.0Gb/s)
       *	Gen3 signaling speed (6.0Gb/s)
       *	Native Command Queueing (NCQ)
       *	Host-initiated interface power management
       *	Phy event counters
       *	DMA Setup Auto-Activate optimization
            Device-initiated interface power management
       *	Software settings preservation
       *	SMART Command Transport (SCT) feature set
       *	SCT Data Tables (AC5)
       *	reserved 69[4]
       *	Data Set Management TRIM supported (limit 1 block)
       *	Deterministic read data after TRIM
"""

HDPARM_AFTER_SECURITY = b"""\
Logical Unit WWN Device Identifier: 55cd2e40002643cf
    NAA		: 5
    IEEE OUI	: 5cd2e4
    Unique ID	: 0002643cf
Checksum: correct
"""

HDPARM_SECURITY_NOT_SUPPORTED = b"""\
Security:
    Master password revision code = 65534
    not supported
    not enabled
    not locked
    not frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""

HDPARM_SECURITY_SUPPORTED_NOT_ENABLED = b"""\
Security:
    Master password revision code = 65534
        supported
    not enabled
    not locked
    not frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""

HDPARM_SECURITY_SUPPORTED_ENABLED = b"""\
Security:
    Master password revision code = 65534
        supported
        enabled
    not locked
    not frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""

HDPARM_SECURITY_ALL_TRUE = b"""\
Security:
    Master password revision code = 65534
        supported
        enabled
        locked
        frozen
    not	expired: security count
        supported: enhanced erase
    4min for SECURITY ERASE UNIT. 2min for ENHANCED SECURITY ERASE UNIT.
"""


class TestMAASWipe(MAASTestCase):
    def setUp(self):
        super(TestMAASWipe, self).setUp()
        self.print_flush = self.patch(maas_wipe, "print_flush")

    def make_empty_file(self, path, content=b"\0"):
        assert len(content) == 1
        # Make an empty 100 MiB file.
        buf = content * 1024 * 1024
        with open(path, "wb") as fp:
            for _ in range(5):
                fp.write(buf)

    def test_list_disks_calls_lsblk(self):
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.return_value = b""
        list_disks()
        self.assertThat(
            mock_check_output,
            MockCalledOnceWith(["lsblk", "-d", "-n", "-oKNAME,TYPE,RO"]),
        )

    def test_list_disks_returns_only_readwrite_disks(self):
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.return_value = dedent(
            """\
            sda   disk  0
            sdb   disk  1
            sr0   rom   0
            sr1   rom   0
            """
        ).encode("ascii")
        self.assertEqual([b"sda"], list_disks())

    def test_get_disk_security_info_missing(self):
        hdparm_output = HDPARM_BEFORE_SECURITY + HDPARM_AFTER_SECURITY
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.return_value = hdparm_output
        disk_name = factory.make_name("disk").encode("ascii")
        observered = get_disk_security_info(disk_name)
        self.assertThat(
            mock_check_output,
            MockCalledOnceWith([b"hdparm", b"-I", b"/dev/%s" % disk_name]),
        )
        self.assertEqual(
            {
                b"supported": False,
                b"enabled": False,
                b"locked": False,
                b"frozen": False,
            },
            observered,
        )

    def test_get_disk_security_info_not_supported(self):
        hdparm_output = (
            HDPARM_BEFORE_SECURITY
            + HDPARM_SECURITY_NOT_SUPPORTED
            + HDPARM_AFTER_SECURITY
        )
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.return_value = hdparm_output
        disk_name = factory.make_name("disk").encode("ascii")
        observered = get_disk_security_info(disk_name)
        self.assertThat(
            mock_check_output,
            MockCalledOnceWith([b"hdparm", b"-I", b"/dev/%s" % disk_name]),
        )
        self.assertEqual(
            {
                b"supported": False,
                b"enabled": False,
                b"locked": False,
                b"frozen": False,
            },
            observered,
        )

    def test_get_disk_security_info_supported_not_enabled(self):
        hdparm_output = (
            HDPARM_BEFORE_SECURITY
            + HDPARM_SECURITY_SUPPORTED_NOT_ENABLED
            + HDPARM_AFTER_SECURITY
        )
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.return_value = hdparm_output
        disk_name = factory.make_name("disk").encode("ascii")
        observered = get_disk_security_info(disk_name)
        self.assertThat(
            mock_check_output,
            MockCalledOnceWith([b"hdparm", b"-I", b"/dev/%s" % disk_name]),
        )
        self.assertEqual(
            {
                b"supported": True,
                b"enabled": False,
                b"locked": False,
                b"frozen": False,
            },
            observered,
        )

    def test_get_disk_security_info_supported_enabled(self):
        hdparm_output = (
            HDPARM_BEFORE_SECURITY
            + HDPARM_SECURITY_SUPPORTED_ENABLED
            + HDPARM_AFTER_SECURITY
        )
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.return_value = hdparm_output
        disk_name = factory.make_name("disk").encode("ascii")
        observered = get_disk_security_info(disk_name)
        self.assertThat(
            mock_check_output,
            MockCalledOnceWith([b"hdparm", b"-I", b"/dev/%s" % disk_name]),
        )
        self.assertEqual(
            {
                b"supported": True,
                b"enabled": True,
                b"locked": False,
                b"frozen": False,
            },
            observered,
        )

    def test_get_disk_security_info_all_true(self):
        hdparm_output = (
            HDPARM_BEFORE_SECURITY
            + HDPARM_SECURITY_ALL_TRUE
            + HDPARM_AFTER_SECURITY
        )
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.return_value = hdparm_output
        disk_name = factory.make_name("disk").encode("ascii")
        observered = get_disk_security_info(disk_name)
        self.assertThat(
            mock_check_output,
            MockCalledOnceWith([b"hdparm", b"-I", b"/dev/%s" % disk_name]),
        )
        self.assertEqual(
            {
                b"supported": True,
                b"enabled": True,
                b"locked": True,
                b"frozen": True,
            },
            observered,
        )

    def test_get_disk_info(self):
        disk_names = [
            factory.make_name("disk").encode("ascii") for _ in range(3)
        ]
        self.patch(maas_wipe, "list_disks").return_value = disk_names
        security_info = [
            {
                b"supported": True,
                b"enabled": True,
                b"locked": True,
                b"frozen": True,
            }
            for _ in range(3)
        ]
        self.patch(
            maas_wipe, "get_disk_security_info"
        ).side_effect = security_info
        observed = get_disk_info()
        self.assertEqual(
            {disk_names[i]: security_info[i] for i in range(3)}, observed
        )

    def test_try_secure_erase_not_supported(self):
        disk_name = factory.make_name("disk").encode("ascii")
        disk_info = {
            b"supported": False,
            b"enabled": False,
            b"locked": False,
            b"frozen": False,
        }
        self.assertFalse(try_secure_erase(disk_name, disk_info))
        self.assertThat(
            self.print_flush,
            MockCalledOnceWith(
                "%s: drive does not support secure erase."
                % (disk_name.decode("ascii"))
            ),
        )

    def test_try_secure_erase_frozen(self):
        disk_name = factory.make_name("disk").encode("ascii")
        disk_info = {
            b"supported": True,
            b"enabled": False,
            b"locked": False,
            b"frozen": True,
        }
        self.assertFalse(try_secure_erase(disk_name, disk_info))
        self.assertThat(
            self.print_flush,
            MockCalledOnceWith(
                "%s: not using secure erase; drive is currently frozen."
                % (disk_name.decode("ascii"))
            ),
        )

    def test_try_secure_erase_locked(self):
        disk_name = factory.make_name("disk").encode("ascii")
        disk_info = {
            b"supported": True,
            b"enabled": False,
            b"locked": True,
            b"frozen": False,
        }
        self.assertFalse(try_secure_erase(disk_name, disk_info))
        self.assertThat(
            self.print_flush,
            MockCalledOnceWith(
                "%s: not using secure erase; drive is currently locked."
                % (disk_name.decode("ascii"))
            ),
        )

    def test_try_secure_erase_enabled(self):
        disk_name = factory.make_name("disk").encode("ascii")
        disk_info = {
            b"supported": True,
            b"enabled": True,
            b"locked": False,
            b"frozen": False,
        }
        self.assertFalse(try_secure_erase(disk_name, disk_info))
        self.assertThat(
            self.print_flush,
            MockCalledOnceWith(
                "%s: not using secure erase; drive security "
                "is already enabled." % (disk_name.decode("ascii"))
            ),
        )

    def test_try_secure_erase_failed_erase(self):
        disk_name = factory.make_name("disk").encode("ascii")
        disk_info = {
            b"supported": True,
            b"enabled": False,
            b"locked": False,
            b"frozen": False,
        }
        exception = factory.make_exception()
        self.patch(maas_wipe, "secure_erase").side_effect = exception
        self.assertFalse(try_secure_erase(disk_name, disk_info))
        self.assertThat(
            self.print_flush,
            MockCalledOnceWith(
                "%s: failed to be securely erased: %s"
                % (disk_name.decode("ascii"), exception)
            ),
        )

    def test_try_secure_erase_successful_erase(self):
        disk_name = factory.make_name("disk").encode("ascii")
        disk_info = {
            b"supported": True,
            b"enabled": False,
            b"locked": False,
            b"frozen": False,
        }
        self.patch(maas_wipe, "secure_erase")
        self.assertTrue(try_secure_erase(disk_name, disk_info))
        self.assertThat(
            self.print_flush,
            MockCalledOnceWith(
                "%s: successfully securely erased."
                % (disk_name.decode("ascii"))
            ),
        )

    def test_secure_erase_writes_known_data(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path)

        # Fail at the set-pass to stop the function.
        mock_check_output = self.patch(subprocess, "check_output")
        mock_check_output.side_effect = factory.make_exception()

        self.assertRaises(WipeError, secure_erase, dev_name)
        expected_buf = b"M" * 1024 * 1024
        with open(file_path, "rb") as fp:
            read_buf = fp.read(len(expected_buf))
        self.assertEqual(
            expected_buf, read_buf, "First 1 MiB of file was not written."
        )

    def test_secure_erase_sets_security_password(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path)

        mock_check_output = self.patch(subprocess, "check_output")

        # Fail to get disk info just to exit early.
        exception_type = factory.make_exception_type()
        self.patch(
            maas_wipe, "get_disk_security_info"
        ).side_effect = exception_type()

        self.assertRaises(exception_type, secure_erase, dev_name)
        self.assertThat(
            mock_check_output,
            MockCalledOnceWith(
                [
                    b"hdparm",
                    b"--user-master",
                    b"u",
                    b"--security-set-pass",
                    b"maas",
                    file_path,
                ]
            ),
        )

    def test_secure_erase_fails_if_not_enabled(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path)

        self.patch(subprocess, "check_output")
        self.patch(maas_wipe, "get_disk_security_info").return_value = {
            b"enabled": False
        }

        error = self.assertRaises(WipeError, secure_erase, dev_name)
        self.assertEqual(
            "Failed to enable security to perform secure erase.", str(error)
        )

    def test_secure_erase_fails_when_still_enabled(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path)

        mock_check_output = self.patch(subprocess, "check_output")
        self.patch(maas_wipe, "get_disk_security_info").return_value = {
            b"enabled": True
        }
        exception = factory.make_exception()
        mock_check_call = self.patch(subprocess, "check_call")
        mock_check_call.side_effect = exception

        error = self.assertRaises(WipeError, secure_erase, dev_name)
        self.assertThat(
            mock_check_call,
            MockCalledOnceWith(
                [
                    b"hdparm",
                    b"--user-master",
                    b"u",
                    b"--security-erase",
                    b"maas",
                    file_path,
                ]
            ),
        )
        self.assertThat(
            mock_check_output,
            MockCallsMatch(
                call(
                    [
                        b"hdparm",
                        b"--user-master",
                        b"u",
                        b"--security-set-pass",
                        b"maas",
                        file_path,
                    ]
                ),
                call([b"hdparm", b"--security-disable", b"maas", file_path]),
            ),
        )
        self.assertEqual("Failed to securely erase.", str(error))
        self.assertEqual(exception, error.__cause__)

    def test_secure_erase_fails_when_buffer_not_different(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path)

        self.patch(subprocess, "check_output")
        self.patch(maas_wipe, "get_disk_security_info").side_effect = [
            {b"enabled": True},
            {b"enabled": False},
        ]
        mock_check_call = self.patch(subprocess, "check_call")

        error = self.assertRaises(WipeError, secure_erase, dev_name)
        self.assertThat(
            mock_check_call,
            MockCalledOnceWith(
                [
                    b"hdparm",
                    b"--user-master",
                    b"u",
                    b"--security-erase",
                    b"maas",
                    file_path,
                ]
            ),
        )
        self.assertEqual(
            "Secure erase was performed, but failed to actually work.",
            str(error),
        )

    def test_secure_erase_fails_success(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path)

        self.patch(subprocess, "check_output")
        self.patch(maas_wipe, "get_disk_security_info").side_effect = [
            {b"enabled": True},
            {b"enabled": False},
        ]

        def wipe_buffer(*args, **kwargs):
            # Write the first 1 MiB to zeros so it looks like the device
            # has been securely erased.
            buf = b"\0" * 1024 * 1024
            with open(file_path, "wb") as fp:
                fp.write(buf)

        mock_check_call = self.patch(subprocess, "check_call")
        mock_check_call.side_effect = wipe_buffer

        # No error should be raised.
        secure_erase(dev_name)

    def test_wipe_quickly(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path, content=b"T")

        wipe_quickly(dev_name)

        buf_size = 1024 * 1024
        with open(file_path, "rb") as fp:
            first_buf = fp.read(buf_size)
            fp.seek(-buf_size, 2)
            last_buf = fp.read(buf_size)

        zero_buf = b"\0" * 1024 * 1024
        self.assertEqual(zero_buf, first_buf, "First 1 MiB was not wiped.")
        self.assertEqual(zero_buf, last_buf, "Last 1 MiB was not wiped.")

    def test_zero_disk(self):
        tmp_dir = self.make_dir()
        dev_path = (tmp_dir + "/%s").encode("ascii")
        self.patch(maas_wipe, "DEV_PATH", dev_path)
        dev_name = factory.make_name("disk").encode("ascii")
        file_path = dev_path % dev_name
        self.make_empty_file(file_path, content=b"T")

        # Add a little size to the file making it not evenly
        # divisable by 1 MiB.
        extra_end = 512
        with open(file_path, "a+b") as fp:
            fp.write(b"T" * extra_end)

        zero_disk(dev_name)

        zero_buf = b"\0" * 1024 * 1024
        with open(file_path, "rb") as fp:
            fp.seek(0, 2)
            size = fp.tell()
            fp.seek(0, 0)

            count = size // len(zero_buf)
            for i in range(count):
                buf = fp.read(len(zero_buf))
                self.assertEqual(zero_buf, buf, "%d block was not wiped." % i)

            extra_buf = fp.read(extra_end)
            self.assertEqual(
                b"\0" * extra_end, extra_buf, "End was not wiped."
            )

    def patch_args(self, secure_erase, quick_erase):
        args = MagicMock()
        args.secure_erase = secure_erase
        args.quick_erase = quick_erase
        parser = MagicMock()
        parser.parse_args.return_value = args
        self.patch(argparse, "ArgumentParser").return_value = parser

    def test_main_calls_try_secure_erase_for_all_disks(self):
        self.patch_args(True, False)
        disks = {
            factory.make_name("disk").encode("ascii"): {} for _ in range(3)
        }
        self.patch(maas_wipe, "get_disk_info").return_value = disks

        mock_zero = self.patch(maas_wipe, "zero_disk")
        mock_try = self.patch(maas_wipe, "try_secure_erase")
        mock_try.return_value = True
        maas_wipe.main()

        calls = [call(disk, info) for disk, info in disks.items()]
        self.assertThat(mock_try, MockCallsMatch(*calls))
        self.assertThat(mock_zero, MockNotCalled())

    def test_main_calls_zero_disk_if_no_secure_erase(self):
        self.patch_args(True, False)
        disks = {
            factory.make_name("disk").encode("ascii"): {} for _ in range(3)
        }
        self.patch(maas_wipe, "get_disk_info").return_value = disks

        mock_zero = self.patch(maas_wipe, "zero_disk")
        mock_try = self.patch(maas_wipe, "try_secure_erase")
        mock_try.return_value = False
        maas_wipe.main()

        try_calls = [call(disk, info) for disk, info in disks.items()]
        wipe_calls = [call(disk) for disk in disks.keys()]
        self.assertThat(mock_try, MockCallsMatch(*try_calls))
        self.assertThat(mock_zero, MockCallsMatch(*wipe_calls))

    def test_main_calls_wipe_quickly_if_no_secure_erase(self):
        self.patch_args(True, True)
        disks = {
            factory.make_name("disk").encode("ascii"): {} for _ in range(3)
        }
        self.patch(maas_wipe, "get_disk_info").return_value = disks

        wipe_quickly = self.patch(maas_wipe, "wipe_quickly")
        mock_try = self.patch(maas_wipe, "try_secure_erase")
        mock_try.return_value = False
        maas_wipe.main()

        try_calls = [call(disk, info) for disk, info in disks.items()]
        wipe_calls = [call(disk) for disk in disks.keys()]
        self.assertThat(mock_try, MockCallsMatch(*try_calls))
        self.assertThat(wipe_quickly, MockCallsMatch(*wipe_calls))

    def test_main_calls_wipe_quickly(self):
        self.patch_args(False, True)
        disks = {
            factory.make_name("disk").encode("ascii"): {} for _ in range(3)
        }
        self.patch(maas_wipe, "get_disk_info").return_value = disks

        wipe_quickly = self.patch(maas_wipe, "wipe_quickly")
        mock_try = self.patch(maas_wipe, "try_secure_erase")
        mock_try.return_value = False
        maas_wipe.main()

        wipe_calls = [call(disk) for disk in disks.keys()]
        self.assertThat(mock_try, MockNotCalled())
        self.assertThat(wipe_quickly, MockCallsMatch(*wipe_calls))

    def test_main_calls_zero_disk(self):
        self.patch_args(False, False)
        disks = {
            factory.make_name("disk").encode("ascii"): {} for _ in range(3)
        }
        self.patch(maas_wipe, "get_disk_info").return_value = disks

        zero_disk = self.patch(maas_wipe, "zero_disk")
        mock_try = self.patch(maas_wipe, "try_secure_erase")
        mock_try.return_value = False
        maas_wipe.main()

        wipe_calls = [call(disk) for disk in disks.keys()]
        self.assertThat(mock_try, MockNotCalled())
        self.assertThat(zero_disk, MockCallsMatch(*wipe_calls))

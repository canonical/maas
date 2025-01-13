from argparse import Namespace
import os
from unittest.mock import call, MagicMock, patch

from metadataserver.builtin_scripts.release_scripts.maas_wipe import (
    clean_mdadm,
    main,
    secure_erase_hdparm,
    stop_bcache,
    stop_lvm,
    try_secure_erase_hdparm,
    try_secure_erase_nvme,
    wipe_quickly,
)


class TestMaasWipe:

    # Patches here defined in order in which they're executed within `main()`
    @patch("argparse.ArgumentParser.parse_args")
    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.get_disk_info"
    )
    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.stop_bcache"
    )
    @patch("metadataserver.builtin_scripts.release_scripts.maas_wipe.stop_lvm")
    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.clean_mdadm"
    )
    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.wipe_quickly"
    )
    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.zero_disk"
    )
    def test_main_quick_erase_cleans_special_filesystems(
        self,
        zero_disk_mock: MagicMock,
        wipe_quickly_mock: MagicMock,
        clean_mdadm_mock: MagicMock,
        stop_lvm_mock: MagicMock,
        stop_bcache_mock: MagicMock,
        get_disk_info_mock: MagicMock,
        arg_parse_mock: MagicMock,
    ) -> None:
        # NOTE: Patched objects are passed to the test function in the reverse
        # order to which they are defined above in the decorators.

        # Setup a quick disk erase
        arg_parse_mock.return_value = Namespace(
            quick_erase=True, secure_erase=False
        )

        get_disk_info_mock.return_value = {
            b"nvme0n1": {
                "format_supported": True,
                "crypto_format": False,
                "lbaf": 0,
                "ms": 0,
            }
        }

        stop_bcache_mock.return_value = None
        stop_lvm_mock.return_value = None
        clean_mdadm_mock.return_value = None

        # Call the script
        main()

        # Check the filesystem clearing functions were called on a quick erase
        arg_parse_mock.assert_called_once()
        get_disk_info_mock.assert_called_once()

        stop_bcache_mock.assert_called_once()
        stop_lvm_mock.assert_called_once()
        clean_mdadm_mock.assert_called_once()

        zero_disk_mock.assert_not_called()
        wipe_quickly_mock.assert_called_once_with(b"nvme0n1")

    @patch("os.path.exists")
    @patch("os.listdir")
    @patch("os.path.isdir")
    def test_stop_bcache(
        self,
        os_path_isdir_mock: MagicMock,
        os_listdir_mock: MagicMock,
        os_path_exists_mock: MagicMock,
    ) -> None:
        os_path_exists_mock.return_value = True

        # bcache name from bug report (lp #2057782)
        os_listdir_mock.return_value = ["3427372a-636a-408c-b4cb-f65c185e4022"]

        os_path_isdir_mock.return_value = True

        with patch("builtins.open") as m:
            stop_bcache()

            m.assert_has_calls(
                [
                    call(
                        "/sys/fs/bcache/3427372a-636a-408c-b4cb-f65c185e4022/stop",
                        "w",
                    ),
                    call().write("1"),
                    call().close(),
                ]
            )

    @patch("subprocess.check_output")
    def test_stop_lvm(self, check_output_mock: MagicMock) -> None:
        stop_lvm()
        check_output_mock.assert_called_once_with(["vgchange", "-a", "n"])

    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.list_raids"
    )
    @patch("subprocess.check_output")
    def test_clean_mdadm(
        self,
        check_output_mock: MagicMock,
        list_raids_mock: MagicMock,
    ) -> None:
        list_raids_mock.return_value = [b"md0"]

        clean_mdadm()

        check_output_mock.assert_has_calls(
            [
                call(["wipefs", "-f", "-a", b"/dev/md0"]),
                call(["mdadm", "--stop", b"md0"]),
            ]
        )

    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.list_partitions"
    )
    @patch("subprocess.check_output")
    def test_wipe_quickly(
        self,
        check_output_mock: MagicMock,
        list_part_mock: MagicMock,
    ) -> None:
        partitions = [b"nvme0n1p1", b"nvme0n1p2", b"nvme0n1p3"]

        list_part_mock.return_value = partitions

        check_output_mock.return_value = None

        with patch("builtins.open") as m:
            wipe_quickly(b"nvme0n1")

            # Verify first and last 2MiB are zeroed
            buf = b"\0" * 1024 * 1024 * 2  # 2 MiB
            m.assert_has_calls(
                [
                    call(b"/dev/nvme0n1", "wb"),
                    call().write(buf),
                    call().seek(-len(buf), 2),
                    call().write(buf),
                ]
            )

        # Verify all partitions and then the drive are called in `wipefs``
        check_output_mock.assert_has_calls(
            [
                call(["wipefs", "-f", "-a", b"/dev/nvme0n1p1"]),
                call(["wipefs", "-f", "-a", b"/dev/nvme0n1p2"]),
                call(["wipefs", "-f", "-a", b"/dev/nvme0n1p3"]),
                call(["wipefs", "-f", "-a", b"/dev/nvme0n1"]),
            ]
        )

    @patch("subprocess.check_output")
    def test_try_secure_erase_nvme_supported(
        self,
        check_output_mock: MagicMock,
    ) -> None:
        # Disk info representing an unencrypted nvme drive
        disk_info = {
            "format_supported": True,
            "crypto_format": False,
            "lbaf": 0,
            "ms": 0,
        }

        check_output_mock.return_value = None

        wiped = try_secure_erase_nvme(b"nvme0n1", disk_info)

        assert wiped

        check_output_mock.assert_called_once_with(
            [
                "nvme",
                "format",
                "-s",
                "1",
                "-l",
                str(disk_info["lbaf"]),
                "-m",
                str(disk_info["ms"]),
                b"/dev/nvme0n1",
            ]
        )

    def test_try_secure_erase_nvme_unsupported(self) -> None:
        disk_info = {
            "format_supported": False,
        }

        wiped = try_secure_erase_nvme(b"nvme0n1", disk_info)

        assert not wiped

    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.secure_erase_hdparm"
    )
    def test_try_secure_erase_hdparm_supported(
        self,
        secure_erase_hdparm_mock: MagicMock,
    ) -> None:
        disk_info = {
            b"supported": True,
            b"frozen": False,
            b"locked": False,
            b"enabled": False,
        }

        secure_erase_hdparm_mock.return_value = None

        wiped = try_secure_erase_hdparm(b"sda", disk_info)

        assert wiped

        secure_erase_hdparm_mock.assert_called_once_with(b"sda")

    def test_try_secure_erase_hdparm_unsupported(self) -> None:
        disk_info = {
            b"supported": False,
        }

        wiped = try_secure_erase_hdparm(b"sda", disk_info)

        assert not wiped

    @patch("mmap.mmap")
    @patch("os.open")
    @patch("os.write")
    @patch("os.close")
    @patch("subprocess.check_output")
    @patch(
        "metadataserver.builtin_scripts.release_scripts.maas_wipe.get_hdparm_security_info"
    )
    @patch("subprocess.check_call")
    @patch("os.fdopen")
    def test_secure_erase_hdparm(
        self,
        os_fdopen_mock: MagicMock,
        check_call_mock: MagicMock,
        get_hdparm_sec_info_mock: MagicMock,
        check_output_mock: MagicMock,
        os_close_mock: MagicMock,
        os_write_mock: MagicMock,
        os_open_mock: MagicMock,
        mmap_mock: MagicMock,
    ) -> None:
        sze = 1024 * 1024
        buf = b"M" * sze

        # Two os.open() calls in code so two different fds
        os_open_mock.side_effect = [64, 65]

        get_hdparm_sec_info_mock.side_effect = [
            {
                b"supported": True,
                b"frozen": False,
                b"locked": False,
                b"enabled": True,
            },
            {
                b"supported": True,
                b"frozen": False,
                b"locked": False,
                b"enabled": False,
            },
        ]

        secure_erase_hdparm(b"sda")

        # Check the logic of a successful erasure
        # Assertions are a bit interleaved due to need for has_calls API but
        # their relative order is fine.
        os_open_mock.assert_has_calls(
            [
                call(b"/dev/sda", os.O_WRONLY | os.O_SYNC | os.O_DIRECT),
                call(b"/dev/sda", os.O_RDONLY | os.O_SYNC | os.O_DIRECT),
            ]
        )
        os_write_mock.assert_called_once_with(64, mmap_mock())
        os_close_mock.assert_called_once_with(64)

        mmap_mock.assert_has_calls(
            [
                call(-1, sze),
                call().write(buf),
                call().close(),
                call(-1, sze),
                call().read(len(buf)),
                call().close(),
            ]
        )

        check_output_mock.assert_has_calls(
            [
                call(
                    [
                        b"hdparm",
                        b"--user-master",
                        b"u",
                        b"--security-set-pass",
                        b"maas",
                        b"/dev/sda",
                    ]
                ),
            ]
        )

        check_call_mock.assert_has_calls(
            [
                call(
                    [
                        b"hdparm",
                        b"--user-master",
                        b"u",
                        b"--security-erase",
                        b"maas",
                        b"/dev/sda",
                    ]
                ),
            ]
        )

        os_fdopen_mock.assert_has_calls(
            [
                call(65, "rb"),
                call().readinto(mmap_mock()),
            ]
        )

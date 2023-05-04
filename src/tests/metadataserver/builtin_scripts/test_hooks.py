import pytest

from metadataserver.builtin_scripts.hooks import parse_bootif_cmdline


class TestParseBootifCmdline:
    @pytest.mark.parametrize(
        "cmdline,expected",
        [
            ("BOOTIF=01-aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
            ("BOOTIF=01-aa-bb-cc-dd-ee-ff", "aa:bb:cc:dd:ee:ff"),
            ("BOOTIF=garbage", None),
            ("BOOTIF=01-aa-bb-cc-dd-ee", None),
        ],
    )
    def test_parse(self, cmdline, expected):
        assert parse_bootif_cmdline(cmdline) == expected

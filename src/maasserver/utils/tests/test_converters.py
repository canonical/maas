# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for converters utilities."""


from datetime import timedelta
from textwrap import dedent

from maasserver.utils.converters import (
    human_readable_bytes,
    machine_readable_bytes,
    parse_systemd_interval,
    round_size_to_nearest_block,
    systemd_interval_to_calendar,
    XMLToYAML,
)
from maastesting.testcase import MAASTestCase


class TestXMLToYAML(MAASTestCase):
    def test_xml_to_yaml_converts_xml(self):
        # This test is similar to the test above but this one
        # checks that tags with colons works as expected.
        xml = """
        <list xmlns:lldp="lldp" xmlns:lshw="lshw">
         <lldp:lldp label="LLDP neighbors"/>
         <lshw:list>Some Content</lshw:list>
        </list>
        """
        expected_result = dedent(
            """\
        - list:
          - lldp:lldp:
            label: LLDP neighbors
          - lshw:list:
            Some Content
        """
        )
        yml = XMLToYAML(xml)
        self.assertEqual(yml.convert(), expected_result)


class TestHumanReadableBytes(MAASTestCase):
    scenarios = [
        ("bytes", dict(size=987, output="987", suffix="bytes")),
        ("kB", dict(size=1000 * 35 + 500, output="35.5", suffix="kB")),
        ("MB", dict(size=(1000**2) * 28, output="28.0", suffix="MB")),
        ("GB", dict(size=(1000**3) * 72, output="72.0", suffix="GB")),
        ("TB", dict(size=(1000**4) * 150, output="150.0", suffix="TB")),
        ("PB", dict(size=(1000**5), output="1.0", suffix="PB")),
        ("EB", dict(size=(1000**6), output="1.0", suffix="EB")),
        ("ZB", dict(size=(1000**7), output="1.0", suffix="ZB")),
        ("YB", dict(size=(1000**8), output="1.0", suffix="YB")),
    ]

    def test_returns_size_with_suffix(self):
        self.assertEqual(
            f"{self.output} {self.suffix}",
            human_readable_bytes(self.size),
        )

    def test_returns_size_without_suffix(self):
        self.assertEqual(
            self.output, human_readable_bytes(self.size, include_suffix=False)
        )


class TestMachineReadableBytes(MAASTestCase):
    """Testing the human->machine byte count converter"""

    def test_suffixes(self):
        self.assertEqual(machine_readable_bytes("987"), 987)
        self.assertEqual(machine_readable_bytes("987K"), 987000)
        self.assertEqual(machine_readable_bytes("987M"), 987000000)
        self.assertEqual(machine_readable_bytes("987G"), 987000000000)
        self.assertEqual(machine_readable_bytes("987T"), 987000000000000)
        self.assertEqual(machine_readable_bytes("987P"), 987000000000000000)
        self.assertEqual(machine_readable_bytes("987E"), 987000000000000000000)
        self.assertEqual(machine_readable_bytes("987k"), 987000)
        self.assertEqual(machine_readable_bytes("987m"), 987000000)
        self.assertEqual(machine_readable_bytes("987g"), 987000000000)
        self.assertEqual(machine_readable_bytes("987t"), 987000000000000)
        self.assertEqual(machine_readable_bytes("987p"), 987000000000000000)
        self.assertEqual(machine_readable_bytes("987e"), 987000000000000000000)

        self.assertRaises(ValueError, machine_readable_bytes, "987Z")


class TestRoundSizeToNearestBlock(MAASTestCase):
    def test_round_up_adds_extra_block(self):
        block_size = 4096
        size = block_size + 1
        self.assertEqual(
            2 * block_size,
            round_size_to_nearest_block(size, block_size, True),
            "Should add an extra block to the size.",
        )

    def test_round_up_doesnt_add_extra_block(self):
        block_size = 4096
        size = block_size
        self.assertEqual(
            size,
            round_size_to_nearest_block(size, block_size, True),
            "Shouldn't add an extra block to the size.",
        )

    def test_round_down_removes_block(self):
        block_size = 4096
        size = block_size + 1
        self.assertEqual(
            1 * block_size,
            round_size_to_nearest_block(size, block_size, False),
            "Should remove block from the size.",
        )

    def test_round_down_doesnt_remove_block(self):
        block_size = 4096
        size = block_size * 2
        self.assertEqual(
            size,
            round_size_to_nearest_block(size, block_size, False),
            "Shouldn't remove a block from the size.",
        )


class TestParseSystemdInterval(MAASTestCase):
    def _assert_parsed(
        self, interval: str, hours: int = 0, minutes: int = 0, seconds: int = 0
    ):
        expected_seconds = timedelta(
            hours=hours, minutes=minutes, seconds=seconds
        ).total_seconds()
        out = parse_systemd_interval(interval)
        self.assertEqual(expected_seconds, out)

    def test_parses_full_plural_word_durations(self):
        self._assert_parsed(
            "2 hours 5 minutes 10 seconds", hours=2, minutes=5, seconds=10
        )

    def test_parses_full_word_durations(self):
        self._assert_parsed(
            "1 hour 1 minute 1 second", hours=1, minutes=1, seconds=1
        )

    def test_parses_abbreviated_durations(self):
        self._assert_parsed("1hr 15min 5sec", hours=1, minutes=15, seconds=5)

    def test_parses_initials_durations(self):
        self._assert_parsed("3h 5m 2s", hours=3, minutes=5, seconds=2)

    def test_parses_single_full_plural_duration(self):
        self._assert_parsed("5 minutes", minutes=5)

    def test_parses_single_full_duration(self):
        self._assert_parsed("1 hours", hours=1)

    def test_parses_single_abbreviated_duration(self):
        self._assert_parsed("5min", minutes=5)

    def test_parses_single_initials_duration(self):
        self._assert_parsed("15s", seconds=15)


class TestSystemdIntervalToCalendar(MAASTestCase):
    def test_every_2_hours(self):
        interval = "2h"
        self.assertEqual(
            "*-*-* 00/2:00:00", systemd_interval_to_calendar(interval)
        )

    def test_every_hour(self):
        interval = "1h"
        self.assertEqual(
            "*-*-* *:00:00", systemd_interval_to_calendar(interval)
        )

    def test_every_hour_and_a_half(self):
        interval = "1h 30m"
        self.assertEqual(
            "*-*-* *:00/30:00", systemd_interval_to_calendar(interval)
        )

    def test_every_30_minutes(self):
        interval = "30m"
        self.assertEqual(
            "*-*-* *:00/30:00", systemd_interval_to_calendar(interval)
        )

    def test_every_30_minutes_5_seconds(self):
        interval = "30m 5s"
        self.assertEqual(
            "*-*-* *:00/30:00/5", systemd_interval_to_calendar(interval)
        )

    def test_every_15_seconds(self):
        interval = "15s"
        self.assertEqual(
            "*-*-* *:*:00/15", systemd_interval_to_calendar(interval)
        )

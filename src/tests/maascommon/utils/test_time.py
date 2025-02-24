#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

from maascommon.utils.time import systemd_interval_to_seconds


class TestParseSystemdInterval:
    def _assert_parsed(
        self, interval: str, hours: int = 0, minutes: int = 0, seconds: int = 0
    ):
        expected_seconds = timedelta(
            hours=hours, minutes=minutes, seconds=seconds
        ).total_seconds()
        out = systemd_interval_to_seconds(interval)
        assert expected_seconds == out

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

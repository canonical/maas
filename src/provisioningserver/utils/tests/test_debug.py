from datetime import datetime
import io
import os
from pathlib import Path
import pstats

from fixtures import EnvironmentVariableFixture, TempDir
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import debug
from provisioningserver.utils.debug import (
    register_sigusr1_toggle_cprofile,
    toggle_cprofile,
)


class TestToggleCprofile(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.now = datetime(2019, 1, 31, 1, 2, 3, 4)
        self.datetime_mock = self.patch(debug, "datetime")
        self.datetime_mock.now.return_value = self.now
        self.maas_root = self.useFixture(TempDir()).path
        self.useFixture(
            EnvironmentVariableFixture("MAAS_ROOT", self.maas_root)
        )

    def _get_prof_path(self, process_name):
        return (
            Path(self.maas_root)
            / "var"
            / "lib"
            / "maas"
            / "profiling"
            / f"{process_name}-{os.getpid()}-2019-01-31T01:02:03.000004.pyprof"
        )

    def test_toggle_cprofile_writes_file(self):
        toggle_cprofile("my-process")
        toggle_cprofile("my-process")
        self.assertTrue(self._get_prof_path("my-process").exists())

    def test_toggle_cprofile_profiles(self):
        def my_method():
            return 1

        toggle_cprofile("my-process")
        my_method()
        toggle_cprofile("my-process")
        prof_path = self._get_prof_path("my-process")
        output = io.StringIO()
        stats = pstats.Stats(str(prof_path), stream=output)
        stats.print_callers()
        self.assertIn("my_method", output.getvalue())

    def test_register_sigusr1(self):
        mock_signal = self.patch(debug.signal, "signal")
        register_sigusr1_toggle_cprofile("my-process")
        print(mock_signal.signal.mock_calls)
        [(_, args, kwargs)] = mock_signal.mock_calls
        self.assertEqual({}, kwargs)
        signal, func = args
        self.assertEqual(signal.SIGUSR1, signal)
        func()
        func()
        self.assertTrue(self._get_prof_path("my-process").exists())

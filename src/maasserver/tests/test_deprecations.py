from pathlib import Path

from fixtures import EnvironmentVariable

from maasserver.deprecations import get_deprecations, log_deprecations
from maastesting.testcase import MAASTestCase
from provisioningserver.logger import LegacyLogger


class TestGetDeprecations(MAASTestCase):
    def test_empty(self):
        self.assertEqual(get_deprecations(), [])

    def test_deprecation_notices_snap_not_all_mode(self):
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        snap_common_path = Path(self.make_dir())
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )
        snap_common_path.joinpath("snap_mode").write_text(
            "region+rack", "utf-8"
        )
        self.assertEqual(get_deprecations(), [])

    def test_deprecation_notices_snap_all_mode(self):
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        snap_common_path = Path(self.make_dir())
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )
        snap_common_path.joinpath("snap_mode").write_text("all", "utf-8")
        [notice] = get_deprecations()
        self.assertEqual(notice["id"], "MD1")
        self.assertEqual(notice["since"], "2.8")
        self.assertEqual(notice["url"], "https://maas.io/deprecations/MD1")


class TestLogDeprecations(MAASTestCase):
    def test_log_deprecations(self):
        self.useFixture(EnvironmentVariable("SNAP", "/snap/maas/current"))
        snap_common_path = Path(self.make_dir())
        self.useFixture(
            EnvironmentVariable("SNAP_COMMON", str(snap_common_path))
        )
        snap_common_path.joinpath("snap_mode").write_text("all", "utf-8")

        events = []
        logger = LegacyLogger(observer=events.append)
        log_deprecations(logger=logger)
        [event] = events
        self.assertEqual(
            event["_message_0"],
            "Deprecation MD1 (https://maas.io/deprecations/MD1): "
            "The setup for this MAAS is deprecated and not suitable for production "
            "environments, as the database is running inside the snap.",
        )

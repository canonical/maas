# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasserver.models import ControllerInfo, Notification
from maasserver.models.controllerinfo import (
    get_maas_version,
    get_target_version,
    TargetVersion,
    UPGRADE_ISSUE_NOTIFICATION_IDENT,
    UPGRADE_STATUS_NOTIFICATION_IDENT,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.enum import CONTROLLER_INSTALL_TYPE
from provisioningserver.utils.deb import DebVersionsInfo
from provisioningserver.utils.snap import SnapChannel, SnapVersionsInfo
from provisioningserver.utils.version import MAASVersion


class TestControllerInfo(MAASServerTestCase):
    def test_str(self):
        controller = factory.make_RackController(hostname="foobar")
        info, _ = ControllerInfo.objects.update_or_create(node=controller)
        self.assertEqual("ControllerInfo (foobar)", str(info))

    def test_set_version(self):
        controller = factory.make_RackController()
        ControllerInfo.objects.set_version(controller, "2.3.0")
        self.assertEqual(controller.version, "2.3.0")

    def test_set_versions_info_snap(self):
        controller = factory.make_RackController()
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            channel={"track": "3.0", "risk": "stable"},
            update={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
            cohort="abc123",
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = controller.controllerinfo
        self.assertEqual(
            controller_info.install_type, CONTROLLER_INSTALL_TYPE.SNAP
        )
        self.assertEqual(
            controller_info.version, "3.0.0~alpha1-111-g.deadbeef"
        )
        self.assertEqual(
            controller_info.update_version, "3.0.0~alpha2-222-g.cafecafe"
        )
        self.assertEqual(controller_info.update_origin, "3.0/stable")
        self.assertEqual(controller_info.snap_revision, "1234")
        self.assertEqual(controller_info.snap_update_revision, "5678")
        self.assertEqual(controller_info.snap_cohort, "abc123")
        self.assertIsNotNone(controller_info.update_first_reported)

    def test_set_versions_info_snap_no_update(self):
        controller = factory.make_RackController()
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            channel={"track": "3.0", "risk": "stable"},
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = controller.controllerinfo
        self.assertEqual(controller_info.update_origin, "3.0/stable")
        self.assertEqual(controller_info.snap_update_revision, "")
        self.assertEqual(controller_info.snap_cohort, "")
        self.assertIsNone(controller_info.update_first_reported)

    def test_set_versions_info_deb(self):
        controller = factory.make_RackController()
        versions = DebVersionsInfo(
            current={
                "version": "3.0.0~alpha1-111-g.deadbeef",
                "origin": "http://archive.ubuntu.com/ focal/main",
            },
            update={
                "version": "3.0.0~alpha2-222-g.cafecafe",
                "origin": "http://mymirror.example.com/ focal/main",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = controller.controllerinfo
        self.assertEqual(
            controller_info.install_type, CONTROLLER_INSTALL_TYPE.DEB
        )
        self.assertEqual(
            controller_info.version, "3.0.0~alpha1-111-g.deadbeef"
        )
        self.assertEqual(
            controller_info.update_version, "3.0.0~alpha2-222-g.cafecafe"
        )
        # the origin for the update is used
        self.assertEqual(
            controller_info.update_origin,
            "http://mymirror.example.com/ focal/main",
        )
        self.assertEqual(controller_info.snap_revision, "")
        self.assertEqual(controller_info.snap_update_revision, "")
        self.assertEqual(controller_info.snap_cohort, "")
        self.assertIsNotNone(controller_info.update_first_reported)

    def test_set_versions_info_deb_no_update(self):
        controller = factory.make_RackController()
        versions = DebVersionsInfo(
            current={
                "version": "3.0.0~alpha1-111-g.deadbeef",
                "origin": "http://archive.ubuntu.com/ focal/main",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = controller.controllerinfo
        self.assertEqual(controller_info.update_version, "")
        self.assertEqual(
            controller_info.update_origin,
            "http://archive.ubuntu.com/ focal/main",
        )
        self.assertIsNone(controller_info.update_first_reported)

    def test_set_versions_info_deb_ppa(self):
        controller = factory.make_RackController()
        versions = DebVersionsInfo(
            current={
                "version": "3.0.0~alpha1-111-g.deadbeef",
                "origin": "http://ppa.launchpad.net/maas/3.0/ubuntu/ focal/main",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        self.assertEqual(
            controller.controllerinfo.update_origin,
            "ppa:maas/3.0",
        )

    def test_set_versions_info_deb_ppa_update(self):
        controller = factory.make_RackController()
        versions = DebVersionsInfo(
            current={
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "version": "3.0.1-222-g.cafecafe",
                "origin": "http://ppa.launchpad.net/maas/3.0/ubuntu/ focal/main",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        self.assertEqual(
            controller.controllerinfo.update_origin,
            "ppa:maas/3.0",
        )

    def test_set_versions_info_change_type(self):
        controller = factory.make_RackController()
        deb_versions = DebVersionsInfo(
            current={
                "version": "3.0.0",
                "origin": "http://archive.ubuntu.com/ focal/main",
            },
            update={
                "version": "3.0.1",
                "origin": "http://mymirror.example.com/ focal/main",
            },
        )
        snap_versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.1.0",
            },
            channel={"track": "3.0", "risk": "stable"},
            update={
                "revision": "5678",
                "version": "3.1.1",
            },
            cohort="abc123",
        )
        ControllerInfo.objects.set_versions_info(controller, deb_versions)
        ControllerInfo.objects.set_versions_info(controller, snap_versions)
        controller_info = reload_object(controller).controllerinfo
        # all fields are updated
        self.assertEqual(
            controller_info.install_type, CONTROLLER_INSTALL_TYPE.SNAP
        )
        self.assertEqual(controller_info.version, "3.1.0")
        self.assertEqual(controller_info.update_version, "3.1.1")
        self.assertEqual(controller_info.update_origin, "3.0/stable")
        self.assertEqual(controller_info.snap_revision, "1234")
        self.assertEqual(controller_info.snap_update_revision, "5678")
        self.assertEqual(controller_info.snap_cohort, "abc123")

    def test_set_versions_update_first_reported_update_same_update(self):
        controller = factory.make_RackController()
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        update_first_reported = controller.controllerinfo.update_first_reported
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        controller_info = reload_object(controller).controllerinfo
        self.assertEqual(
            controller_info.update_first_reported, update_first_reported
        )

    def test_set_versions_update_first_reported_update_different_update(self):
        controller = factory.make_RackController()
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        update_first_reported = controller.controllerinfo.update_first_reported
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "revision": "5678",
                "version": "3.0.0~alpha3-333-g.adadadad",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = reload_object(controller).controllerinfo
        self.assertGreater(
            controller_info.update_first_reported, update_first_reported
        )

    def test_set_versions_update_first_reported_update_same_update_different_install_type(
        self,
    ):
        controller = factory.make_RackController()
        versions = DebVersionsInfo(
            current={
                "version": "3.0.0~alpha1-111-g.deadbeef",
                "origin": "http://archive.ubuntu.com/ focal/main",
            },
            update={
                "version": "3.0.0~alpha2-222-g.cafecafe",
                "origin": "http://archive.ubuntu.com/ focal/main",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        update_first_reported = controller.controllerinfo.update_first_reported
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = reload_object(controller).controllerinfo
        self.assertGreater(
            controller_info.update_first_reported, update_first_reported
        )

    def test_set_versions_update_first_reported_no_update(self):
        controller = factory.make_RackController()
        versions = SnapVersionsInfo(
            current={
                "revision": "1234",
                "version": "3.0.0~alpha1-111-g.deadbeef",
            },
            update={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        versions = SnapVersionsInfo(
            current={
                "revision": "5678",
                "version": "3.0.0~alpha2-222-g.cafecafe",
            },
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = reload_object(controller).controllerinfo
        self.assertIsNone(controller_info.update_first_reported)

    def test_is_up_to_date(self):
        version = "3.0.0~alpha1-111-g.deadbeef"
        target_version = TargetVersion(
            version=MAASVersion.from_string(version),
            snap_channel="3.0/stable",
        )
        controller = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            controller,
            SnapVersionsInfo(
                current={
                    "revision": "1234",
                    "version": version,
                },
            ),
        )
        self.assertTrue(controller.info.is_up_to_date(target_version))

    def test_is_up_to_date_with_update(self):
        version = "3.0.0~alpha1-111-g.deadbeef"
        target_version = TargetVersion(
            version=MAASVersion.from_string(version),
            snap_channel="3.0/stable",
        )
        controller = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            controller,
            SnapVersionsInfo(
                current={
                    "revision": "1234",
                    "version": version,
                },
                update={
                    "revision": "5678",
                    "version": "3.0.0-222-g.cafecafe",
                },
            ),
        )
        self.assertFalse(controller.info.is_up_to_date(target_version))

    def test_is_up_to_date_with_different_version(self):
        target_version = TargetVersion(
            version=MAASVersion.from_string("3.0.0-222-g.cafecafe"),
            snap_channel="3.0/stable",
        )
        controller = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            controller,
            SnapVersionsInfo(
                current={
                    "revision": "1234",
                    "version": "3.0.0~alpha1-111-g.deadbeef",
                },
            ),
        )
        self.assertFalse(controller.info.is_up_to_date(target_version))


class TestGetTargetVersion(MAASServerTestCase):
    def test_empty(self):
        factory.make_RackController()
        self.assertIsNone(get_target_version())

    def test_return_highest_version(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        c3 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(current={"version": "3.0.0~alpha1-111-g.aaa"}),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(current={"version": "3.0.0~beta1-222-g.bbb"}),
        )
        ControllerInfo.objects.set_versions_info(
            c3,
            DebVersionsInfo(current={"version": "3.0.0-333-g.ccc"}),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-333-g.ccc"),
                snap_channel=SnapChannel.from_string("3.0/stable"),
                first_reported=None,
            ),
        )

    def test_return_highest_update(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        c3 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "2.9.0-001-g.zzz"},
                update={"version": "3.0.0~alpha1-111-g.aaa"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(
                current={"version": "2.9.0-001-g.zzz"},
                update={"version": "3.0.0~beta1-222-g.bbb"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c3,
            DebVersionsInfo(
                current={"version": "2.9.0-001-g.zzz"},
                update={"version": "3.0.0-333-g.ccc"},
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-333-g.ccc"),
                snap_channel=SnapChannel.from_string("3.0/stable"),
                first_reported=c3.info.update_first_reported,
            ),
        )

    def test_update_return_earliest_reported(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        c3 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "2.9.0-001-g.zzz"},
                update={"version": "3.0.0~alpha1-111-g.aaa"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(
                current={"version": "2.9.0-001-g.zzz"},
                update={"version": "3.0.0-333-g.ccc"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c3,
            DebVersionsInfo(
                current={"version": "2.9.0-001-g.zzz"},
                update={"version": "3.0.0-333-g.ccc"},
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-333-g.ccc"),
                snap_channel=SnapChannel.from_string("3.0/stable"),
                first_reported=c2.info.update_first_reported,
            ),
        )

    def test_update_older_than_installed(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111-g.aaa"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(
                current={"version": "2.9.0-001-g.zzz"},
                update={"version": "2.9.1-010-g.bbb"},
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-111-g.aaa"),
                snap_channel=SnapChannel.from_string("3.0/stable"),
                first_reported=None,
            ),
        )

    def test_snap_channel(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "stable"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "beta"},
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-111-g.aaa"),
                snap_channel=SnapChannel("3.0", "beta"),
                first_reported=None,
            ),
        )

    def test_snap_channel_no_branch(self):
        controller = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            controller,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "beta", "branch": "mybranch"},
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-111-g.aaa"),
                snap_channel=SnapChannel.from_string("3.0/beta"),
                first_reported=None,
            ),
        )

    def test_snap_channel_keep_release_branch(self):
        controller = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            controller,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={
                    "track": "3.0",
                    "risk": "beta",
                    "branch": "ubuntu-20.04",
                },
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-111-g.aaa"),
                snap_channel=SnapChannel.from_string("3.0/beta/ubuntu-20.04"),
                first_reported=None,
            ),
        )

    def test_snap_channel_from_version(self):
        c1 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0~rc1-111-g.aaa"},
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0~rc1-111-g.aaa"),
                snap_channel=SnapChannel("3.0", "candidate"),
                first_reported=None,
            ),
        )

    def test_snap_channel_ignores_deb(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "stable"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(
                current={
                    "version": "3.0.0~beta1-001-g.bbb",
                    "origin": "http://archive.ubuntu.com/ focal/main",
                },
                update={
                    "version": "3.0.0-111-g.aaa",
                    "origin": "http://archive.ubuntu.com/ focal/main",
                },
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-111-g.aaa"),
                snap_channel=SnapChannel("3.0", "stable"),
                first_reported=None,
            ),
        )

    def test_snap_cohort_from_target_version(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                cohort="abc",
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.1-222-g.bbb", "revision": "5678"},
                cohort="xyz",
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.1-222-g.bbb"),
                snap_channel=SnapChannel("3.0", "stable"),
                snap_cohort="xyz",
            ),
        )

    def test_snap_cohort_from_update(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                cohort="abc",
                update={"version": "3.0.2-333-g.ccc", "revision": "7890"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.1-222-g.bbb", "revision": "5678"},
                cohort="xyz",
            ),
        )
        target_version = get_target_version()
        self.assertEqual(target_version.snap_cohort, "abc")

    def test_snap_cohort_multiple_cohorts_target_version(self):
        c1 = factory.make_RackController()
        c2 = factory.make_RackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                cohort="abc",
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                cohort="xyz",
            ),
        )
        self.assertEqual(
            get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-111-g.aaa"),
                snap_channel=SnapChannel("3.0", "stable"),
                snap_cohort="",
            ),
        )


class TestGetMAASVersion(MAASServerTestCase):
    def test_no_versions(self):
        factory.make_RegionRackController()
        factory.make_RegionRackController()
        self.assertIsNone(get_maas_version())

    def test_version_with_highest_count(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c1, "3.0.0")
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c2, "3.0.0")
        c3 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c3, "3.1.0")
        self.assertEqual(get_maas_version(), MAASVersion.from_string("3.0.0"))

    def test_highest_version_same_count(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c1, "3.0.0")
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c2, "3.1.0")
        self.assertEqual(get_maas_version(), MAASVersion.from_string("3.1.0"))

    def test_combine_versions_up_to_qualifier(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c1, "3.0.0~beta1-123-g.asdf")
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c2, "3.0.0~beta2-456-g.cafe")
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c2, "3.0.0~beta2-789-g.abcd")
        c3 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c3, "3.1.0")
        self.assertEqual(
            get_maas_version(), MAASVersion.from_string("3.0.0~beta2")
        )


class TestUpdateVersionNotifications(MAASServerTestCase):
    def test_same_upgrade(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111-g.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(
                current={"version": "3.0.0-111-g.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        self.assertFalse(
            Notification.objects.filter(
                ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
            ).exists()
        )

    def test_different_versions(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111-g.aaa"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(
                current={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification = Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).first()
        self.assertIn(
            "Controllers have different versions.",
            notification.message,
        )

    def test_different_upgrades(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111-g.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            DebVersionsInfo(
                current={"version": "3.0.0-111-g.aaa"},
                update={"version": "3.0.2-333-g.ccc"},
            ),
        )
        notification = Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).first()
        self.assertIn(
            "Controllers report different upgrade versions.",
            notification.message,
        )

    def test_different_install_types(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111-g.aaa"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
            ),
        )
        notification = Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).first()
        self.assertIn(
            "Controllers have different installation sources.",
            notification.message,
        )

    def test_different_origins(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "stable"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "beta"},
            ),
        )
        notification = Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).first()
        self.assertIn(
            "Controllers have different installation sources.",
            notification.message,
        )

    def test_different_snap_cohorts(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                cohort="abc",
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                cohort="xyz",
            ),
        )
        notification = Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).first()
        self.assertIn(
            "Controllers have different installation sources.",
            notification.message,
        )

    def test_issue_resolved_removes_notification(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                cohort="abc",
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
            ),
        )
        self.assertTrue(
            Notification.objects.filter(
                ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
            ).exists()
        )
        # remove the cohort
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
            ),
        )
        self.assertFalse(
            Notification.objects.filter(
                ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
            ).exists()
        )

    def test_different_issue_new_notification(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "stable"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.0-111-g.aaa", "revision": "1234"},
                channel={"track": "3.0", "risk": "beta"},
            ),
        )
        notification1 = Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).first()
        self.assertIn(
            "Controllers have different installation sources.",
            notification1.message,
        )
        ControllerInfo.objects.set_versions_info(
            c2,
            SnapVersionsInfo(
                current={"version": "3.0.2-222-g.bbb", "revision": "5678"},
                channel={"track": "3.0", "risk": "stable"},
            ),
        )
        notification2 = Notification.objects.filter(
            ident=UPGRADE_ISSUE_NOTIFICATION_IDENT
        ).first()
        self.assertIn(
            "Controllers have different versions.",
            notification2.message,
        )
        self.assertNotEqual(notification1.id, notification2.id)

    def test_update_status_update_available(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(notification.category, "info")
        self.assertEqual(
            notification.render(),
            "MAAS 3.0.1 is available, controllers will upgrade soon.",
        )
        self.assertEqual(
            notification.context,
            {"status": "inprogress", "version": "3.0.1"},
        )

    def test_update_status_update_same_version(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification1 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(
            notification1.render(),
            "MAAS 3.0.1 is available, controllers will upgrade soon.",
        )
        # report again, same version
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification2 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(
            notification2.render(),
            "MAAS 3.0.1 is available, controllers will upgrade soon.",
        )
        self.assertEqual(
            notification2.context,
            {"status": "inprogress", "version": "3.0.1"},
        )
        self.assertEqual(notification1.id, notification2.id)

    def test_update_status_update_new_version(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification1 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(
            notification1.render(),
            "MAAS 3.0.1 is available, controllers will upgrade soon.",
        )
        # report again, but new upgrade version
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.2-333-g.ccc"},
            ),
        )
        notification2 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(
            notification2.render(),
            "MAAS 3.0.2 is available, controllers will upgrade soon.",
        )
        self.assertEqual(
            notification2.context,
            {"status": "inprogress", "version": "3.0.2"},
        )
        self.assertNotEqual(notification1.id, notification2.id)

    def test_update_status_update_completed(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification1 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification2 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(notification2.category, "success")
        self.assertEqual(
            notification2.render(),
            "MAAS has been updated to version 3.0.1.",
        )
        self.assertEqual(
            notification2.context,
            {"status": "completed", "version": "3.0.1"},
        )
        self.assertNotEqual(notification1.id, notification2.id)

    def test_update_status_update_already_completed(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification1 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        # report again, but with no change
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification2 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(
            notification2.render(),
            "MAAS has been updated to version 3.0.1.",
        )
        self.assertEqual(
            notification2.context,
            {"status": "completed", "version": "3.0.1"},
        )
        self.assertEqual(notification1.id, notification2.id)

    def test_update_status_new_update_already_completed(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.0-111.aaa"},
                update={"version": "3.0.1-222-g.bbb"},
            ),
        )
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.1-222-g.bbb"},
            ),
        )
        notification1 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        # a new update is available
        ControllerInfo.objects.set_versions_info(
            c1,
            DebVersionsInfo(
                current={"version": "3.0.1-222-g.bbb"},
                update={"version": "3.0.2-333-g.ccc"},
            ),
        )
        notification2 = Notification.objects.filter(
            ident=UPGRADE_STATUS_NOTIFICATION_IDENT,
        ).first()
        self.assertEqual(
            notification2.render(),
            "MAAS 3.0.2 is available, controllers will upgrade soon.",
        )
        self.assertEqual(
            notification2.context,
            {"status": "inprogress", "version": "3.0.2"},
        )
        self.assertNotEqual(notification1.id, notification2.id)

# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasserver.models import ControllerInfo, Notification
from maasserver.models.controllerinfo import (
    TargetVersion,
    UPGRADE_ISSUE_NOTIFICATION_IDENT,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.enum import CONTROLLER_INSTALL_TYPE
from provisioningserver.utils.deb import DebVersionsInfo
from provisioningserver.utils.snap import SnapVersionsInfo
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

    def test_get_target_version_return_highest_version(self):
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
            ControllerInfo.objects.get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-333-g.ccc"),
                first_reported=None,
            ),
        )

    def test_get_target_version_return_highest_update(self):
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
            ControllerInfo.objects.get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-333-g.ccc"),
                first_reported=c3.info.update_first_reported,
            ),
        )

    def test_get_target_version_update_return_earliest_reported(self):
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
            ControllerInfo.objects.get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-333-g.ccc"),
                first_reported=c2.info.update_first_reported,
            ),
        )

    def test_get_target_version_update_older_than_installed(self):
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
            ControllerInfo.objects.get_target_version(),
            TargetVersion(
                version=MAASVersion.from_string("3.0.0-111-g.aaa"),
            ),
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

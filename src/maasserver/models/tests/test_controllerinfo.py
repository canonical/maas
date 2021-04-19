# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from testtools.matchers import Equals, Is

from maasserver.models import ControllerInfo, Notification
from maasserver.models.controllerinfo import (
    ControllerVersionInfo,
    create_or_update_version_notification,
    KNOWN_VERSION_MISMATCH_NOTIFICATION,
    TargetVersion,
    UNKNOWN_VERSION_MISMATCH_NOTIFICATION,
    VERSION_NOTIFICATION_IDENT,
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
        self.assertThat(controller.version, Equals("2.3.0"))

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
        )
        ControllerInfo.objects.set_versions_info(controller, versions)
        controller_info = controller.controllerinfo
        self.assertEqual(controller_info.update_origin, "")
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
        self.assertEqual(controller_info.update_origin, "")
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


class TestGetControllerVersionInfo(MAASServerTestCase):
    def test_sorts_controllerversioninfo_by_most_recent_version_first(self):
        c1 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c1, "2.3.0")
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c2, "2.4.0")
        c3 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c3, "2.3.5")
        version_info = ControllerInfo.objects.get_controller_version_info()
        # Should have returend a list of ControllerVersionInfo objects.
        for i in range(len(version_info)):
            self.assertThat(
                isinstance(version_info[i], ControllerVersionInfo), Is(True)
            )
        # The versions should be in descending order.
        self.assertThat(version_info[0].version, Equals("2.4.0"))
        self.assertThat(version_info[1].version, Equals("2.3.5"))
        self.assertThat(version_info[2].version, Equals("2.3.0"))


class TestCreateOrUpdateVersionNotification(MAASServerTestCase):
    def test_create(self):
        system_id = "xyzzy"
        create_or_update_version_notification(
            system_id,
            "Fix your MAAS, you slacker! It's only version {ver}.",
            context=dict(ver="1.9"),
        )
        expected_notification = Notification.objects.filter(
            ident=VERSION_NOTIFICATION_IDENT + system_id
        ).first()
        self.assertThat(
            expected_notification.render(),
            Equals("Fix your MAAS, you slacker! It's only version 1.9."),
        )

    def test_update(self):
        system_id = "xyzzy"
        create_or_update_version_notification(
            system_id,
            "Fix your MAAS, you slacker! It's only version {ver}.",
            context=dict(ver="1.9"),
        )
        # The second time should update.
        create_or_update_version_notification(
            system_id,
            "I can't believe you. Still using MAAS {ver}?!",
            context=dict(ver="2.0"),
        )
        expected_notification = Notification.objects.filter(
            ident=VERSION_NOTIFICATION_IDENT + system_id
        ).first()
        self.assertThat(
            expected_notification.render(),
            Equals("I can't believe you. Still using MAAS 2.0?!"),
        )


def get_version_notifications():
    return Notification.objects.filter(
        ident__startswith=VERSION_NOTIFICATION_IDENT
    )


class TestUpdateVersionNotifications(MAASServerTestCase):
    def test_single_controller_never_generates_notifications(self):
        c1 = factory.make_RegionRackController()
        self.assertThat(get_version_notifications().count(), Equals(0))
        ControllerInfo.objects.set_version(c1, "2.3.0")
        self.assertFalse(get_version_notifications().exists())

    def test_out_of_date_controller_generates_concise_notification(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c1, "2.3.0-500-g1")
        ControllerInfo.objects.set_version(c2, "2.3.1-500-g1")
        self.assertThat(get_version_notifications().count(), Equals(1))
        self.assertThat(
            get_version_notifications().first().render(),
            Equals(
                KNOWN_VERSION_MISMATCH_NOTIFICATION.format(
                    system_id=c1.system_id, hostname=c1.hostname, v1="2.3.0"
                )
            ),
        )

    def test_version_qualifiers_considered(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        # Note: the revno and git revision are intentionally identical here,
        # so we know they don't affect the comparison of qualifiers, and we
        # know that useless information won't appear in the notification.
        ControllerInfo.objects.set_version(c1, "2.3.0~alpha1-500-g1")
        ControllerInfo.objects.set_version(c2, "2.3.0~alpha2-500-g1")
        self.assertThat(get_version_notifications().count(), Equals(1))
        self.assertThat(
            get_version_notifications().first().render(),
            Equals(
                KNOWN_VERSION_MISMATCH_NOTIFICATION.format(
                    system_id=c1.system_id,
                    hostname=c1.hostname,
                    v1="2.3.0~alpha1",
                )
            ),
        )

    def test_assumes_old_controller_if_version_unknown(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c1, "2.3.0")
        self.assertThat(get_version_notifications().count(), Equals(1))
        self.assertThat(
            get_version_notifications().first().render(),
            Equals(
                UNKNOWN_VERSION_MISMATCH_NOTIFICATION.format(
                    system_id=c2.system_id, hostname=c2.hostname
                )
            ),
        )

    def test_revno_differences_cause_full_version_to_be_shown(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionRackController()
        ControllerInfo.objects.set_version(c1, "2.3.0~beta2-6000-g.123abc")
        ControllerInfo.objects.set_version(c2, "2.3.0~beta2-6001-g.234bcd")
        self.assertThat(get_version_notifications().count(), Equals(1))
        self.assertThat(
            get_version_notifications().first().render(),
            Equals(
                KNOWN_VERSION_MISMATCH_NOTIFICATION.format(
                    system_id=c1.system_id,
                    hostname=c1.hostname,
                    v1="2.3.0~beta2 (6000-g.123abc)",
                )
            ),
        )

    def test_upgrading_controller_causes_old_notifications_to_go_away(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionController()
        ControllerInfo.objects.set_version(c1, "2.3.0~beta2-6000-g123abc")
        ControllerInfo.objects.set_version(c2, "2.3.0~beta2-6001-g234bcd")
        self.assertThat(get_version_notifications().count(), Equals(1))
        ControllerInfo.objects.set_version(c1, "2.3.0~beta2-6001-g234bcd")
        self.assertThat(get_version_notifications().count(), Equals(0))

    def test_deleting_controller_causes_old_notifications_to_go_away(self):
        c1 = factory.make_RegionRackController()
        c2 = factory.make_RegionController()
        ControllerInfo.objects.set_version(c1, "2.3.0~beta2-6000-g123abc")
        ControllerInfo.objects.set_version(c2, "2.3.0~beta2-6001-g234bcd")
        self.assertThat(get_version_notifications().count(), Equals(1))
        c2.delete()
        self.assertThat(get_version_notifications().count(), Equals(0))

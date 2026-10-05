# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from importlib import import_module

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest

from maasserver import deprecations
from maasserver.models import (
    BMC,
    BMCRoutableRackControllerRelationship,
    Node,
    Notification,
    Secret,
    VaultSecret,
)
from maasserver.sqlalchemy import get_sqlalchemy_django_connection

migration = import_module(
    "maasservicelayer.db.alembic.versions.0041_remove_msftocs"
)


def upgrade():
    connection = get_sqlalchemy_django_connection()
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()


def make_old_bmc(factory):
    bmc = factory.make_BMC()
    # Reproduce stored upgrade data without requiring the removed driver.
    BMC.objects.filter(id=bmc.id).update(
        power_type="msftocs",
        power_parameters={"power_address": str(bmc.id), "power_user": "admin"},
    )
    return bmc


@pytest.mark.usefixtures("maasdb")
class TestRemoveMsftocs:
    def test_shared_and_orphan_bmcs_are_removed(self, factory):
        nodes = [
            factory.make_Node(power_type="", with_boot_disk=False)
            for _ in range(2)
        ]
        rack = factory.make_RackController()
        shared = make_old_bmc(factory)
        orphan = make_old_bmc(factory)
        for index, node in enumerate(nodes):
            Node.objects.filter(id=node.id).update(
                bmc_id=shared.id,
                instance_power_parameters={"blade_id": str(index)},
            )
        factory.make_BMCRoutableRackControllerRelationship(shared, rack)
        removed_paths = [
            f"bmc/{bmc.id}/power-parameters" for bmc in (shared, orphan)
        ] + [f"node/{node.id}/power-parameters" for node in nodes]
        for path in removed_paths:
            Secret.objects.create(path=path, value={"power_pass": "old"})
            VaultSecret.objects.create(path=path, deleted=False)
        metadata_path = f"node/{nodes[0].id}/deploy-metadata"
        Secret.objects.create(path=metadata_path, value={"keep": "metadata"})
        VaultSecret.objects.create(path=metadata_path, deleted=False)

        upgrade()

        for node in nodes:
            node.refresh_from_db()
            assert node.bmc_id is None
            assert node.power_type == ""
            assert node.instance_power_parameters == {}
            assert node.get_power_parameters() == {}
            assert node.get_effective_power_info() == (
                False,
                False,
                False,
                False,
                None,
                None,
            )
        assert not BMC.objects.filter(id__in=[shared.id, orphan.id]).exists()
        assert not BMCRoutableRackControllerRelationship.objects.filter(
            bmc_id=shared.id
        ).exists()
        assert not Secret.objects.filter(path__in=removed_paths).exists()
        assert set(
            VaultSecret.objects.filter(path__in=removed_paths).values_list(
                "path", "deleted"
            )
        ) == {(path, True) for path in removed_paths}
        assert Secret.objects.get(path=metadata_path).value == {
            "keep": "metadata"
        }
        assert not VaultSecret.objects.get(path=metadata_path).deleted

    def test_unaffected_configuration_and_secrets_are_preserved(self, factory):
        node = factory.make_Node(
            power_type="ipmi",
            power_parameters={"power_address": "192.0.2.1"},
            with_boot_disk=False,
        )
        make_old_bmc(factory)
        Node.objects.filter(id=node.id).update(
            instance_power_parameters={"power_id": "keep"}
        )
        node.refresh_from_db()
        original_bmc_id = node.bmc_id
        original_parameters = node.bmc.power_parameters
        paths = [
            f"node/{node.id}/power-parameters",
            f"bmc/{node.bmc_id}/power-parameters",
            "global/rpc-shared",
        ]
        for path in paths:
            Secret.objects.update_or_create(
                path=path, defaults={"value": {"secret": "keep"}}
            )
            VaultSecret.objects.create(path=path, deleted=False)
        VaultSecret.objects.create(
            path="bmc/999999/power-parameters", deleted=True
        )

        upgrade()

        node.refresh_from_db()
        assert node.bmc_id == original_bmc_id
        assert node.power_type == "ipmi"
        assert node.bmc.power_parameters == original_parameters
        assert node.instance_power_parameters == {"power_id": "keep"}
        for path in paths:
            assert Secret.objects.get(path=path).value == {"secret": "keep"}
            assert not VaultSecret.objects.get(path=path).deleted
        assert VaultSecret.objects.get(
            path="bmc/999999/power-parameters"
        ).deleted

    def test_notice_survives_cleanup_and_startup(self, factory, mocker):
        make_old_bmc(factory)
        user = factory.make_User()
        admin = factory.make_admin()
        mocker.patch(
            "maasserver.models.notification.can_view_notifications",
            side_effect=lambda account: account.is_superuser,
        )

        upgrade()
        mocker.patch.object(deprecations, "get_deprecations", return_value=[])
        deprecations.sync_deprecation_notifications()
        upgrade()

        notice = Notification.objects.get(ident="power_driver_msftocs_removed")
        assert notice.category == "warning"
        assert notice.dismissable
        assert notice in Notification.objects.find_for_user(user)
        assert notice in Notification.objects.find_for_user(admin)
        assert "Microsoft OCS (msftocs)" in notice.render()
        assert "power configuration has been cleared" in notice.render()
        assert "compatible external service" in notice.render()
        assert (
            "https://discourse.maas.io/t/"
            "creating-a-web-service-for-the-maas-webhook-power-driver/3756"
        ) in notice.render()
        notice.dismiss(user)
        assert notice not in Notification.objects.find_for_user(user)
        assert notice in Notification.objects.find_for_user(admin)

    def test_unaffected_install_has_no_notice(self):
        upgrade()

        assert not Notification.objects.filter(
            ident="power_driver_msftocs_removed"
        ).exists()

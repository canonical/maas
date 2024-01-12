# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from django.core.exceptions import PermissionDenied, ValidationError

from maasserver.enum import INTERFACE_TYPE
from maasserver.models.fabric import Fabric
from maasserver.models.vlan import DEFAULT_VID, DEFAULT_VLAN_NAME, VLAN
from maasserver.permissions import NodePermission
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestFabricManagerGetFabricOr404(MAASServerTestCase):
    def test_user_view_returns_fabric(self):
        user = factory.make_User()
        fabric = factory.make_Fabric()
        self.assertEqual(
            fabric,
            Fabric.objects.get_fabric_or_404(
                fabric.id, user, NodePermission.view
            ),
        )

    def test_user_edit_raises_PermissionError(self):
        user = factory.make_User()
        fabric = factory.make_Fabric()
        self.assertRaises(
            PermissionDenied,
            Fabric.objects.get_fabric_or_404,
            fabric.id,
            user,
            NodePermission.edit,
        )

    def test_user_admin_raises_PermissionError(self):
        user = factory.make_User()
        fabric = factory.make_Fabric()
        self.assertRaises(
            PermissionDenied,
            Fabric.objects.get_fabric_or_404,
            fabric.id,
            user,
            NodePermission.admin,
        )

    def test_admin_view_returns_fabric(self):
        admin = factory.make_admin()
        fabric = factory.make_Fabric()
        self.assertEqual(
            fabric,
            Fabric.objects.get_fabric_or_404(
                fabric.id, admin, NodePermission.view
            ),
        )

    def test_admin_edit_returns_fabric(self):
        admin = factory.make_admin()
        fabric = factory.make_Fabric()
        self.assertEqual(
            fabric,
            Fabric.objects.get_fabric_or_404(
                fabric.id, admin, NodePermission.edit
            ),
        )

    def test_admin_admin_returns_fabric(self):
        admin = factory.make_admin()
        fabric = factory.make_Fabric()
        self.assertEqual(
            fabric,
            Fabric.objects.get_fabric_or_404(
                fabric.id, admin, NodePermission.admin
            ),
        )


class TestFabricManager(MAASServerTestCase):
    def test_default_specifier_matches_id(self):
        factory.make_Fabric()
        fabric = factory.make_Fabric()
        factory.make_Fabric()
        id = fabric.id
        self.assertCountEqual(
            Fabric.objects.filter_by_specifiers("%s" % id), [fabric]
        )

    def test_default_specifier_matches_name_with_id(self):
        factory.make_Fabric()
        fabric = factory.make_Fabric()
        factory.make_Fabric()
        id = fabric.id
        self.assertCountEqual(
            Fabric.objects.filter_by_specifiers("fabric-%s" % id), [fabric]
        )

    def test_default_specifier_matches_name(self):
        factory.make_Fabric()
        fabric = factory.make_Fabric(name="infinite-improbability")
        factory.make_Fabric()
        self.assertCountEqual(
            Fabric.objects.filter_by_specifiers("infinite-improbability"),
            [fabric],
        )

    def test_name_specifier_matches_name(self):
        factory.make_Fabric()
        fabric = factory.make_Fabric(name="infinite-improbability")
        factory.make_Fabric()
        self.assertCountEqual(
            Fabric.objects.filter_by_specifiers("name:infinite-improbability"),
            [fabric],
        )

    def test_class_specifier_matches_class(self):
        factory.make_Fabric(class_type="1 Gbps")
        fabric = factory.make_Fabric(class_type="400 Tbps")
        factory.make_Fabric(class_type="10 Gbps")
        self.assertCountEqual(
            Fabric.objects.filter_by_specifiers("class:400 Tbps"), [fabric]
        )


class TestFabric(MAASServerTestCase):
    def test_get_name_for_empty_name(self):
        fabric = factory.make_Fabric()
        self.assertEqual("fabric-%s" % fabric.id, fabric.get_name())

    def test_invalid_name_raises_exception(self):
        self.assertRaises(
            ValidationError, factory.make_Fabric, name="invalid*name"
        )

    def test_reserved_name_raises_exception(self):
        self.assertRaises(
            ValidationError, factory.make_Fabric, name="fabric-33"
        )

    def test_get_name_for_set_name(self):
        name = factory.make_name("name")
        fabric = factory.make_Fabric(name=name)
        self.assertEqual(name, fabric.get_name())

    def test_creates_fabric_with_default_vlan(self):
        name = factory.make_name("name")
        fabric = factory.make_Fabric(name=name)
        self.assertEqual(name, fabric.name)
        default_vlan = fabric.get_default_vlan()
        self.assertEqual(default_vlan.vid, DEFAULT_VID)
        self.assertEqual(default_vlan.name, DEFAULT_VLAN_NAME)
        self.assertEqual(default_vlan.fabric, fabric)

    def test_get_default_fabric_creates_default_fabric(self):
        default_fabric = Fabric.objects.get_default_fabric()
        self.assertEqual(0, default_fabric.id)
        self.assertEqual("fabric-0", default_fabric.get_name())
        self.assertEqual("fabric-0", default_fabric.name)

    def test_create_sets_name(self):
        fabric = Fabric.objects.create(name=None)
        self.assertEqual("fabric-%d" % fabric.id, fabric.name)

    def test_create_does_not_override_name(self):
        name = factory.make_name()
        fabric = factory.make_Fabric(name=name)
        self.assertEqual(name, fabric.name)

    def test_nonreserved_name_does_not_raise_exception(self):
        fabric = factory.make_Fabric(name="myfabric-33")
        self.assertEqual("myfabric-33", fabric.name)

    def test_rejects_names_with_blanks(self):
        self.assertRaises(
            ValidationError,
            factory.make_Fabric,
            name=factory.make_name("Fabric "),
        )

    def test_rejects_duplicate_names(self):
        fabric1 = factory.make_Fabric()
        self.assertRaises(
            ValidationError, factory.make_Fabric, name=fabric1.name
        )

    def test_get_default_fabric_is_idempotent(self):
        default_fabric = Fabric.objects.get_default_fabric()
        default_fabric2 = Fabric.objects.get_default_fabric()
        self.assertEqual(default_fabric.id, default_fabric2.id)

    def test_is_default_detects_default_fabric(self):
        default_fabric = Fabric.objects.get_default_fabric()
        self.assertTrue(default_fabric.is_default())

    def test_is_default_detects_non_default_fabric(self):
        name = factory.make_name("name")
        fabric = factory.make_Fabric(name=name)
        self.assertFalse(fabric.is_default())

    def test_get_default_vlan_returns_default_vlan(self):
        fabric = factory.make_Fabric()
        factory.make_VLAN(fabric=fabric)
        factory.make_VLAN(fabric=fabric)
        default_vlan = (
            VLAN.objects.filter(fabric=fabric).order_by("id").first()
        )
        first_id = sorted(
            VLAN.objects.filter(fabric=fabric).values_list("id", flat=True)
        )[0]
        self.assertEqual(first_id, default_vlan.id)

    def test_can_delete_nonconnected_fabric(self):
        fabric = factory.make_Fabric()
        fabric.delete()
        self.assertCountEqual([], Fabric.objects.filter(id=fabric.id))

    def test_cant_delete_fabric_if_connected_to_interfaces(self):
        fabric = factory.make_Fabric()
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=fabric.get_default_vlan()
        )
        msg = "Can't delete fabric; the following interfaces are still connected: "

        with self.assertRaisesRegex(ValidationError, msg):
            fabric.delete()

    def test_cant_delete_fabric_if_connected_to_subnet(self):
        fabric = factory.make_Fabric()
        factory.make_Subnet(vlan=fabric.get_default_vlan())
        factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL, vlan=fabric.get_default_vlan()
        )
        msg = "Can't delete fabric; the following subnets are still present: "

        with self.assertRaisesRegex(ValidationError, msg):
            fabric.delete()

    def test_cant_delete_default_fabric(self):
        default_fabric = Fabric.objects.get_default_fabric()
        error = self.assertRaises(ValidationError, default_fabric.delete)
        self.assertEqual(
            "This fabric is the default fabric, it cannot be deleted.",
            error.message,
        )

    def test_can_delete_non_default_fabric(self):
        name = factory.make_name("name")
        fabric = factory.make_Fabric(name=name)
        fabric.vlan_set.all().delete()
        fabric.delete()
        self.assertCountEqual([], Fabric.objects.filter(id=fabric.id))

    def test_save_accepts_default_vlan_in_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        fabric.default_vlan = vlan
        # No exception.
        self.assertIsNone(fabric.save())

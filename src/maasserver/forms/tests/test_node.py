# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for node forms."""

from maasserver.forms import AdminNodeForm, NodeForm
from maasserver.testing.architecture import (
    make_usable_architecture,
    patch_usable_architectures,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks, reload_object


class TestNodeForm(MAASServerTestCase):
    def test_contains_limited_set_of_fields(self):
        form = NodeForm()

        self.assertEqual(
            {"hostname", "domain", "disable_ipv4", "swap_size"},
            form.fields.keys(),
        )

    def test_accepts_hostname(self):
        machine = factory.make_Node()
        hostname = factory.make_string()
        patch_usable_architectures(self, [machine.architecture])

        form = NodeForm(
            data={
                "hostname": hostname,
                "architecture": make_usable_architecture(self),
            },
            instance=machine,
        )

        with post_commit_hooks:
            form.save()

        self.assertEqual(hostname, machine.hostname)

    def test_accepts_domain_by_name(self):
        machine = factory.make_Node()
        domain = factory.make_Domain()
        patch_usable_architectures(self, [machine.architecture])

        form = NodeForm(data={"domain": domain.name}, instance=machine)
        form.save()

        self.assertEqual(domain.name, machine.domain.name)

    def test_accepts_domain_by_id(self):
        machine = factory.make_Node()
        domain = factory.make_Domain()
        patch_usable_architectures(self, [machine.architecture])

        form = NodeForm(data={"domain": domain.id}, instance=machine)
        form.save()

        self.assertEqual(domain.name, machine.domain.name)

    def test_validates_domain(self):
        machine = factory.make_Node()
        patch_usable_architectures(self, [machine.architecture])

        form = NodeForm(
            data={"domain": factory.make_name("domain")}, instance=machine
        )

        self.assertFalse(form.is_valid())

    def test_accepts_disable_ipv4_if_false(self):
        form = NodeForm(
            data={
                "architecture": make_usable_architecture(self),
                "disable_ipv4": False,
            }
        )
        form.save()
        # The field does not get to the model.

    def test_rejects_disable_ipv4_if_true(self):
        form = NodeForm(
            data={
                "architecture": make_usable_architecture(self),
                "disable_ipv4": True,
            }
        )
        self.assertFalse(form.is_valid())


class TestAdminNodeForm(MAASServerTestCase):
    def test_contains_limited_set_of_fields(self):
        user = factory.make_User()
        self.client.login(user=user)
        node = factory.make_Node(owner=user)
        form = AdminNodeForm(instance=node)

        self.assertEqual(
            {
                "hostname",
                "description",
                "domain",
                "disable_ipv4",
                "swap_size",
                "cpu_count",
                "memory",
                "zone",
                "pool",
            },
            form.fields.keys(),
        )

    def test_initialises_zone(self):
        # The zone field uses "to_field_name", so that it can refer to a zone
        # by name instead of by ID.  A bug in Django breaks initialisation
        # from an instance: the field tries to initialise the field using a
        # zone's ID instead of its name, and ends up reverting to the default.
        # The code must work around this bug.
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)
        # We'll create a form that makes a change, but not to the zone.
        data = {"hostname": factory.make_name("host")}
        form = AdminNodeForm(instance=node, data=data)
        # The Django bug would stop the initial field value from being set,
        # but the workaround ensures that it is initialised.
        self.assertEqual(zone.name, form.initial["zone"])

    def test_changes_zone(self):
        node = factory.make_Node()
        zone = factory.make_Zone()
        hostname = factory.make_string()
        form = AdminNodeForm(
            data={
                "hostname": hostname,
                "architecture": make_usable_architecture(self),
                "zone": zone.name,
            },
            instance=node,
        )

        with post_commit_hooks:
            form.save()

        node = reload_object(node)
        self.assertEqual(node.hostname, hostname)
        self.assertEqual(node.zone, zone)

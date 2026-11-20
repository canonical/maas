# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test GlobalDefault objects."""

import random

from maasserver.enum import NODE_STATUS
from maasserver.models import Domain, GlobalDefault
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestGlobalDefault(MAASServerTestCase):
    """Tests for :class:`GlobalDefault`."""

    def test_get_instance_creates_instance_id_0_if_none_exits(self):
        instance = GlobalDefault.objects.instance()
        self.assertEqual(0, instance.id)

    def test_get_instance_returns_existing_id_0(self):
        GlobalDefault.objects.instance()
        instance = GlobalDefault.objects.instance()
        self.assertEqual(0, instance.id)

    def test_returns_default_domain(self):
        instance = GlobalDefault.objects.instance()
        self.assertEqual(Domain.objects.get_default_domain(), instance.domain)

    def test_default_domain_changes_take_effect(self):
        instance = GlobalDefault.objects.instance()
        instance.domain = factory.make_Domain()
        instance.save()
        self.assertEqual(Domain.objects.get_default_domain(), instance.domain)

    def test_nodes_with_previous_default_domain_switch_to_new_default(self):
        global_defaults = GlobalDefault.objects.instance()
        node = factory.make_Node(status=NODE_STATUS.READY)
        self.assertEqual(Domain.objects.get_default_domain(), node.domain)
        global_defaults.domain = factory.make_Domain()
        global_defaults.save()
        node = reload_object(node)
        self.assertEqual(global_defaults.domain, node.domain)

    def test_nodes_with_previous_default_domain_keep_domain_if_deployed(self):
        global_defaults = GlobalDefault.objects.instance()
        node = factory.make_Node(status=NODE_STATUS.DEPLOYED)
        old_default = Domain.objects.get_default_domain()
        self.assertEqual(old_default, node.domain)
        global_defaults.domain = factory.make_Domain()
        global_defaults.save()
        node = reload_object(node)
        self.assertEqual(old_default, node.domain)

    def test_nodes_with_previous_default_domain_keep_domain_if_ephemeral(self):
        global_defaults = GlobalDefault.objects.instance()
        node = factory.make_Node(
            status=random.choice(
                [
                    NODE_STATUS.COMMISSIONING,
                    NODE_STATUS.TESTING,
                    NODE_STATUS.RESCUE_MODE,
                ]
            )
        )
        old_default = Domain.objects.get_default_domain()
        self.assertEqual(old_default, node.domain)
        global_defaults.domain = factory.make_Domain()
        global_defaults.save()
        node = reload_object(node)
        self.assertEqual(old_default, node.domain)

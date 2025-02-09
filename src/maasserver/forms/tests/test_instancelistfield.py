# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `InstanceListField`."""

from django.core.exceptions import ValidationError

from maasserver.forms import InstanceListField
from maasserver.models import Node
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestInstanceListField(MAASServerTestCase):
    """Tests for `InstanceListField`."""

    def test_field_validates_valid_data(self):
        nodes = [factory.make_Node() for _ in range(3)]
        # Create other nodes.
        [factory.make_Node() for _ in range(3)]
        field = InstanceListField(model_class=Node, field_name="system_id")
        input_data = [node.system_id for node in nodes]
        self.assertCountEqual(
            input_data, [node.system_id for node in field.clean(input_data)]
        )

    def test_field_ignores_duplicates(self):
        nodes = [factory.make_Node() for _ in range(2)]
        # Create other nodes.
        [factory.make_Node() for _ in range(3)]
        field = InstanceListField(model_class=Node, field_name="system_id")
        input_data = [node.system_id for node in nodes] * 2
        self.assertCountEqual(
            set(input_data),
            [node.system_id for node in field.clean(input_data)],
        )

    def test_field_rejects_invalid_data(self):
        nodes = [factory.make_Node() for _ in range(3)]
        field = InstanceListField(model_class=Node, field_name="system_id")
        error = self.assertRaises(
            ValidationError,
            field.clean,
            [node.system_id for node in nodes] + ["unknown"],
        )
        self.assertEqual(["Unknown node(s): unknown."], error.messages)

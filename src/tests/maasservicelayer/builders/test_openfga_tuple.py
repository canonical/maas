# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder


class TestOpenFGATupleBuilder:
    def test_default_initialization(self):
        builder = OpenFGATupleBuilder()
        assert builder.populated_fields() == {}

    def test_build_user_member_group(self):
        user_id = "user-123"
        group_id = "group-456"

        builder = OpenFGATupleBuilder.build_user_member_group(
            user_id, group_id
        )

        assert builder.user == f"user:{user_id}"
        assert builder.user_type == "user"
        assert builder.relation == "member"
        assert builder.object_id == group_id
        assert builder.object_type == "group"

    @pytest.mark.parametrize(
        "method_name, relation",
        [
            ("build_group_can_edit_machines_in_pool", "can_edit_machines"),
            ("build_group_can_view_machines_in_pool", "can_view_machines"),
            (
                "build_group_can_view_available_machines_in_pool",
                "can_view_available_machines",
            ),
            ("build_group_can_deploy_machines_in_pool", "can_deploy_machines"),
        ],
    )
    def test_group_pool_scoped_builders(self, method_name, relation):
        group_id = "g1"
        pool_id = "p1"

        method = getattr(OpenFGATupleBuilder, method_name)
        builder = method(group_id, pool_id)

        assert builder.user == f"group:{group_id}#member"
        assert builder.user_type == "userset"
        assert builder.relation == relation
        assert builder.object_id == pool_id
        assert builder.object_type == "pool"

    @pytest.mark.parametrize(
        "method_name, relation",
        [
            ("build_group_can_edit_machines", "can_edit_machines"),
            ("build_group_can_view_machines", "can_view_machines"),
            (
                "build_group_can_view_available_machines",
                "can_view_available_machines",
            ),
            ("build_group_can_deploy_machines", "can_deploy_machines"),
            (
                "build_group_can_view_global_entities",
                "can_view_global_entities",
            ),
            (
                "build_group_can_edit_global_entities",
                "can_edit_global_entities",
            ),
            ("build_group_can_edit_controllers", "can_edit_controllers"),
            ("build_group_can_view_controllers", "can_view_controllers"),
            ("build_group_can_view_identities", "can_view_identities"),
            ("build_group_can_edit_identities", "can_edit_identities"),
            ("build_group_can_view_configurations", "can_view_configurations"),
            ("build_group_can_edit_configurations", "can_edit_configurations"),
            ("build_group_can_edit_notifications", "can_edit_notifications"),
            ("build_group_can_view_notifications", "can_view_notifications"),
            (
                "build_group_can_edit_boot_entities",
                "can_edit_boot_entities",
            ),
            (
                "build_group_can_view_boot_entities",
                "can_view_boot_entities",
            ),
            ("build_group_can_view_devices", "can_view_devices"),
            ("build_group_can_view_ipaddresses", "can_view_ipaddresses"),
        ],
    )
    def test_group_global_scoped_builders(self, method_name, relation):
        group_id = "g1"

        method = getattr(OpenFGATupleBuilder, method_name)
        builder = method(group_id)

        assert builder.user == f"group:{group_id}#member"
        assert builder.user_type == "userset"
        assert builder.relation == relation
        assert builder.object_id == "0"
        assert builder.object_type == "maas"

    def test_build_new_pool(self):
        pool_id = "pool-99"

        builder = OpenFGATupleBuilder.build_pool(pool_id)

        assert builder.user == "maas:0"
        assert builder.user_type == "user"
        assert builder.relation == "parent"
        assert builder.object_id == pool_id
        assert builder.object_type == "pool"

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
            ("build_group_can_edit_pool", "can_edit"),
            ("build_group_can_view_pool", "can_view"),
            ("build_group_can_edit_machines", "can_edit_machines"),
            ("build_group_can_deploy_machines", "can_deploy_machines"),
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
            ("build_group_can_edit_pools", "can_edit_pools"),
            ("build_group_can_view_pools", "can_view_pools"),
            (
                "build_group_can_edit_machines_in_pools",
                "can_edit_machines",
            ),
            (
                "build_group_can_deploy_machines_in_pools",
                "can_deploy_machines",
            ),
            (
                "build_group_can_view_global_entities",
                "can_view_global_entities",
            ),
            (
                "build_group_can_edit_global_entities",
                "can_edit_global_entities",
            ),
            (
                "build_group_can_view_permissions",
                "can_view_permissions",
            ),
            (
                "build_group_can_edit_permissions",
                "can_edit_permissions",
            ),
            (
                "build_group_can_view_configurations",
                "can_view_configurations",
            ),
            (
                "build_group_can_edit_configurations",
                "can_edit_configurations",
            ),
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

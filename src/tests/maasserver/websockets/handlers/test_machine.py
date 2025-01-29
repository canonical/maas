# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from operator import attrgetter

from django.db import transaction
import pytest

from maasserver.enum import NODE_STATUS, NODE_TYPE, SIMPLIFIED_NODE_STATUS
from maasserver.rbac import rbac
from maasserver.storage_layouts import MIN_BOOT_PARTITION_SIZE
from maasserver.testing.factory import factory
from maasserver.websockets.base import HandlerValidationError
from maasserver.websockets.handlers.machine import MachineHandler
from maasserver.websockets.handlers.tests.test_machine import (
    TestMachineHandlerUtils,
)
from maastesting.djangotestcase import count_queries
from metadataserver.enum import (
    HARDWARE_TYPE,
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_TYPE,
)
from provisioningserver.enum import POWER_STATE
from provisioningserver.testing.certificates import get_sample_cert


@pytest.fixture
def force_rbac_off():
    orig_get_url = rbac._get_rbac_url
    rbac._get_rbac_url = lambda: None
    yield
    # clean up
    rbac._get_rbac_url = orig_get_url


@pytest.mark.usefixtures("maasdb")
class TestMachineHandler:
    maxDiff = None

    def _populate_db_for_query_count(self, n=2):
        owner, session = factory.make_User_with_session()
        vlan = factory.make_VLAN(space=factory.make_Space())
        for _ in range(n):
            node = factory.make_Node_with_Interface_on_Subnet(
                owner=owner, vlan=vlan
            )
            commissioning_script_set = factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.COMMISSIONING
            )
            testing_script_set = factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.TESTING
            )
            node.current_commissioning_script_set = commissioning_script_set
            node.current_testing_script_set = testing_script_set
            node.save()
            for __ in range(2):
                factory.make_ScriptResult(
                    status=SCRIPT_STATUS.PASSED,
                    script_set=commissioning_script_set,
                )
                factory.make_ScriptResult(
                    status=SCRIPT_STATUS.PASSED, script_set=testing_script_set
                )
        return owner, session

    # Prevent RBAC from making a query.
    @pytest.mark.usefixtures("force_rbac_off")
    def test_list_ids_num_queries_is_the_expected_number(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")

        owner, session = self._populate_db_for_query_count(2)
        handler = MachineHandler(
            owner, {}, None, session_id=session.session_key
        )
        queries_one, _ = count_queries(handler.list_ids, {"page_size": 1})
        queries_total, _ = count_queries(handler.list_ids, {})
        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        expected_query_count = 4
        assert (
            queries_one == expected_query_count
        ), "Number of queries has changed; make sure this is expected."
        assert (
            queries_total == expected_query_count
        ), "Number of queries has changed; make sure this is expected."

    # Prevent RBAC from making a query.
    @pytest.mark.usefixtures("force_rbac_off")
    def test_list_ids_num_queries_with_filter_is_the_expected_number(
        self, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        owner, session = self._populate_db_for_query_count(2)
        handler = MachineHandler(
            owner, {}, None, session_id=session.session_key
        )
        base_params = {
            "filter": {},
            "group_collapsed": [],
            "group_key": "status",
            "page_number": 1,
            "sort_direction": "descending",
            "sort_key": "hostname",
        }

        queries_one, _ = count_queries(
            handler.list_ids, dict(page_size=1, **base_params)
        )
        queries_total, _ = count_queries(
            handler.list_ids, dict(page_size=50, **base_params)
        )
        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        expected_query_count = 5

        assert (
            queries_one == expected_query_count
        ), "Number of queries has changed; make sure this is expected."
        assert (
            queries_total == expected_query_count
        ), "Number of queries has changed; make sure this is expected."

    def test_list_ids_num_queries_is_the_expected_number_with_rbac(
        self, enable_rbac, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        owner, session = factory.make_User_with_session()
        pool = factory.make_ResourcePool()
        enable_rbac.add_pool(pool)
        enable_rbac.allow(owner.username, pool, "view")
        enable_rbac.allow(owner.username, pool, "admin-machines")

        vlan = factory.make_VLAN(space=factory.make_Space())
        for _ in range(2):
            node = factory.make_Node_with_Interface_on_Subnet(
                owner=owner,
                pool=pool,
                vlan=vlan,
            )
            commissioning_script_set = factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.COMMISSIONING
            )
            testing_script_set = factory.make_ScriptSet(
                node=node, result_type=RESULT_TYPE.TESTING
            )
            node.current_commissioning_script_set = commissioning_script_set
            node.current_testing_script_set = testing_script_set
            node.save()
            for __ in range(2):
                factory.make_ScriptResult(
                    status=SCRIPT_STATUS.PASSED,
                    script_set=commissioning_script_set,
                )
                factory.make_ScriptResult(
                    status=SCRIPT_STATUS.PASSED, script_set=testing_script_set
                )

        handler = MachineHandler(
            owner, {}, None, session_id=session.session_key
        )
        queries_one, _ = count_queries(handler.list_ids, {"page_size": 1})
        queries_total, _ = count_queries(handler.list_ids, {})
        # This check is to notify the developer that a change was made that
        # affects the number of queries performed when doing a node listing.
        # It is important to keep this number as low as possible. A larger
        # number means regiond has to do more work slowing down its process
        # and slowing down the client waiting for the response.
        expected_query_count = 4
        assert (
            queries_one == expected_query_count
        ), "Number of queries has changed; make sure this is expected."
        assert (
            queries_total == expected_query_count
        ), "Number of queries has changed; make sure this is expected."

    def test_cache_clears_on_reload(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        owner, session = factory.make_User_with_session()
        node = factory.make_Node(owner=owner)
        commissioning_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.COMMISSIONING
        )
        testing_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.TESTING
        )
        node.current_commissioning_script_set = commissioning_script_set
        node.current_testing_script_set = testing_script_set
        node.save()
        for _ in range(2):
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED,
                script_set=commissioning_script_set,
            )
            factory.make_ScriptResult(
                status=SCRIPT_STATUS.PASSED, script_set=testing_script_set
            )

        handler = MachineHandler(
            owner, {}, None, session_id=session.session_key
        )
        handler.list_ids({})
        handler.list_ids({})

        # Script results should not be loaded by the machine list action
        assert node.id not in handler._script_results

    def test_list_ids_returns_nodes_only_viewable_by_user(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        other_user, other_user_session_id = factory.make_User_with_session()
        admin, admin_session = factory.make_admin_with_session()
        node = factory.make_Node(status=NODE_STATUS.READY)
        user_node = factory.make_Node(owner=user, status=NODE_STATUS.ALLOCATED)
        other_user_node = factory.make_Node(
            owner=other_user, status=NODE_STATUS.ALLOCATED
        )

        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        list_results = handler.list_ids({})
        assert len(list_results["groups"][0]["items"]) == 2
        assert {node.id, user_node.id} == {
            item["id"] for item in list_results["groups"][0]["items"]
        }

        handler = MachineHandler(
            other_user, {}, None, session_id=other_user_session_id.session_key
        )
        list_results = handler.list_ids({})
        assert len(list_results["groups"][0]["items"]) == 2
        assert {node.id, other_user_node.id} == {
            item["id"] for item in list_results["groups"][0]["items"]
        }

        handler = MachineHandler(
            admin, {}, None, session_id=admin_session.session_key
        )
        list_results = handler.list_ids({})
        assert len(list_results["groups"][0]["items"]) == 3
        assert {node.id, user_node.id, other_user_node.id} == {
            item["id"] for item in list_results["groups"][0]["items"]
        }

    def test_secret_power_params_only_viewable_with_admin_read_permission(
        self, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        admin, admin_session = factory.make_admin_with_session()

        power_address = factory.make_ip_address()
        power_id = factory.make_name("power_id")
        power_pass = factory.make_name("power_pass")
        sanitised_power_params = {
            "power_address": power_address,
            "power_id": power_id,
        }
        full_power_params = sanitised_power_params | {"power_pass": power_pass}
        node = factory.make_Node(
            owner=None, power_parameters=full_power_params
        )

        handler = MachineHandler(
            admin, {}, None, session_id=admin_session.session_key
        )
        node_data = handler.get({"system_id": node.system_id})
        assert node_data["power_parameters"] == full_power_params

        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        node_data = handler.get({"system_id": node.system_id})
        assert node_data["power_parameters"] == sanitised_power_params

    def test_secret_power_params_only_viewable_with_admin_read_permission_rbac(
        self, enable_rbac, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        other_user, other_user_session = factory.make_User_with_session()
        pool = factory.make_ResourcePool()
        enable_rbac.add_pool(pool)
        enable_rbac.allow(user.username, pool, "view")
        enable_rbac.allow(user.username, pool, "admin-machines")
        enable_rbac.allow(other_user.username, pool, "view")

        power_address = factory.make_ip_address()
        power_id = factory.make_name("power_id")
        power_pass = factory.make_name("power_pass")
        sanitised_power_params = {
            "power_address": power_address,
            "power_id": power_id,
        }
        full_power_params = sanitised_power_params | {"power_pass": power_pass}
        node = factory.make_Node(pool=pool, power_parameters=full_power_params)

        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        node_data = handler.get({"system_id": node.system_id})
        assert node_data["power_parameters"] == full_power_params

        handler = MachineHandler(
            other_user, {}, None, session_id=other_user_session.session_key
        )
        node_data = handler.get({"system_id": node.system_id})
        assert node_data["power_parameters"] == sanitised_power_params


@pytest.mark.usefixtures("maasdb")
class TestMachineHandlerNewSchema:
    def test_filter_simple(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        nodes = [
            factory.make_Node(owner=user, status=NODE_STATUS.ALLOCATED)
            for _ in range(3)
        ]
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "filter": {
                    "hostname": [nodes[1].hostname],
                }
            }
        )
        items = result["groups"][0]["items"]
        assert len(items) == 1
        assert items[0]["id"] == nodes[1].id

    def test_filter_composed(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        nodes = [
            factory.make_Node(owner=user, status=NODE_STATUS.ALLOCATED)
            for _ in range(3)
        ]
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "filter": {
                    "hostname": [nodes[1].hostname],
                    "status": "allocated",
                }
            }
        )
        items = result["groups"][0]["items"]
        assert len(items) == 1
        assert items[0]["id"] == nodes[1].id

    def test_filter_no_response(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        for _ in range(3):
            factory.make_Node(owner=user, status=NODE_STATUS.ALLOCATED)
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "filter": {
                    "status": "new",
                }
            }
        )
        assert result["groups"][0]["count"] == 0

    def test_filter_invalid(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        for _ in range(3):
            factory.make_Node(owner=user, status=NODE_STATUS.ALLOCATED)
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        pytest.raises(
            HandlerValidationError,
            handler.list_ids,
            {
                "filter": {
                    "status": "my_custom_status",
                }
            },
        )

    def test_filter_diskless_machine(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        factory.make_Node(
            owner=user, status=NODE_STATUS.NEW, with_boot_disk=False
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "filter": {
                    "status": "new",
                }
            }
        )
        assert result["groups"][0]["count"] == 1

    def test_filter_deployment_target(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        node_with_ephemeral_deployment = factory.make_Node(
            owner=user, status=NODE_STATUS.NEW, ephemeral_deploy=True
        )
        node_with_standard_deployment = factory.make_Node(
            owner=user, status=NODE_STATUS.NEW, ephemeral_deploy=False
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )

        result = handler.list_ids({})
        assert result["groups"][0]["count"] == 2

        result = handler.list_ids(
            {
                "filter": {
                    "deployment_target": ["=memory"],
                }
            }
        )
        assert result["groups"][0]["count"] == 1
        assert (
            result["groups"][0]["items"][0]["id"]
            == node_with_ephemeral_deployment.id
        )

        result = handler.list_ids(
            {
                "filter": {
                    "deployment_target": ["=disk"],
                }
            }
        )
        assert result["groups"][0]["count"] == 1
        assert (
            result["groups"][0]["items"][0]["id"]
            == node_with_standard_deployment.id
        )

    def test_filter_counters(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        nodes = [factory.make_Machine(owner=user) for _ in range(2)]
        for node in nodes:
            _ = [factory.make_PhysicalBlockDevice(node=node) for _ in range(3)]
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids({"group_key": "owner"})
        assert result["count"] == 2
        assert result["groups"][0]["count"] == 2

    def test_filter_storage_counters(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        node = factory.make_Machine(owner=user)
        [node.tags.add(factory.make_Tag()) for _ in range(2)]

        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids({"filter": {"free_text": node.hostname}})

        assert result["count"] == 1
        assert result["groups"][0]["items"][0]["id"] == node.id

    def test_group_label_dynamic(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
            bmc=factory.make_Pod(pod_type="lxd"),
        )
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
            bmc=factory.make_Pod(pod_type="virsh"),
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "pod_type",
            }
        )
        assert result["groups"][0]["name"] == "lxd"
        assert result["groups"][1]["name"] == "virsh"

    def test_group_collapse_dynamic(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
            bmc=factory.make_Pod(pod_type="lxd"),
        )
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
            bmc=factory.make_Pod(pod_type="virsh"),
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "pod_type",
                "group_collapsed": ["lxd"],
            }
        )
        assert result["groups"][0]["name"] == "lxd"
        assert result["groups"][0]["collapsed"]
        assert result["groups"][1]["name"] == "virsh"
        assert not result["groups"][1]["collapsed"]

    def test_group_label_static(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
        )
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.NEW,
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "status",
            }
        )
        assert result["groups"][0]["name"] == "New"
        assert result["groups"][0]["value"] == "new"
        assert result["groups"][1]["name"] == "Allocated"
        assert result["groups"][1]["value"] == "allocated"

    def test_group_simple_status(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        statuses = [
            NODE_STATUS.ALLOCATED,
            NODE_STATUS.FAILED_COMMISSIONING,
            NODE_STATUS.FAILED_DEPLOYMENT,
        ]
        for i in range(3):
            factory.make_Node(owner=user, status=statuses[i])
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "simple_status",
            }
        )
        grp_alloc = result["groups"][0]
        assert grp_alloc["name"] == SIMPLIFIED_NODE_STATUS.ALLOCATED
        assert grp_alloc["value"] == "allocated"
        assert grp_alloc["count"] == 1
        grp_fail = result["groups"][1]
        assert grp_fail["name"] == SIMPLIFIED_NODE_STATUS.FAILED
        assert grp_fail["value"] == "failed"
        assert grp_fail["count"] == 2

    def test_group_power_state(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        factory.make_Node(
            owner=user,
            power_state=POWER_STATE.ON,
        )
        factory.make_Node(
            owner=user,
            power_state=POWER_STATE.OFF,
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "power_state",
            }
        )
        assert result["groups"][0]["name"] == "Off"
        assert result["groups"][1]["name"] == "On"

    def test_group_owner(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        admin, session = factory.make_admin_with_session()
        user1 = factory.make_User(username="User01")
        user2 = factory.make_User(username="User02")
        factory.make_Node(
            owner=user2,
        )
        factory.make_Node(
            owner=user1,
        )
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "owner",
            }
        )
        assert result["groups"][0]["name"] == "User01"
        assert result["groups"][1]["name"] == "User02"

    def test_group_parent(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        admin, session = factory.make_admin_with_session()
        parent = factory.make_Machine(owner=admin)
        for _ in range(2):
            factory.make_Machine(owner=admin, parent=parent)
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "parent",
            }
        )
        assert result["groups"][0]["name"] == parent.hostname
        assert result["groups"][0]["value"] == parent.hostname
        assert result["groups"][0]["count"] == 2
        assert result["groups"][1]["name"] == "None"
        assert result["groups"][1]["value"] is None
        assert result["groups"][1]["count"] == 1

    def test_group_parent_pages_no_parent_first_pagelast(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        # On the first page, the last machine does not have a parent.
        admin, session = factory.make_admin_with_session()
        parent = factory.make_Machine(owner=admin)
        factory.make_Machine(owner=admin, parent=parent)
        factory.make_Machine(owner=admin, parent=parent)
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "parent",
                "page_size": 2,
                "page_number": 1,
            }
        )
        assert len(result["groups"]) == 1
        assert len(result["groups"][0]["items"]) == 2
        assert parent.id not in [
            item["id"] for item in result["groups"][0]["items"]
        ]

    def test_group_parent_pages_no_parent_previous_page_with_parent(
        self, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        # On the second page, the top has no parent, previous page
        # ended with a machine with a parent
        admin, session = factory.make_admin_with_session()
        parent = factory.make_Machine(owner=admin)
        factory.make_Machine(owner=admin, parent=parent)
        factory.make_Machine(owner=admin, parent=parent)
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "parent",
                "page_size": 2,
                "page_number": 2,
            }
        )
        assert len(result["groups"]) == 1
        assert len(result["groups"][0]["items"]) == 1
        assert parent.id == result["groups"][0]["items"][0]["id"]

    def test_group_parent_pages_with_parent_previous_page_with_parent_and_no_parent(
        self, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        # On the second page, the top of the page has a parent, but there
        # should machines with no parents included as well.
        admin, session = factory.make_admin_with_session()
        parent1 = factory.make_Machine(owner=admin)
        parent2 = factory.make_Machine(owner=admin)
        factory.make_Machine(owner=admin, parent=parent1)
        factory.make_Machine(owner=admin, parent=parent1)
        factory.make_Machine(owner=admin, parent=parent1)
        factory.make_Machine(owner=admin, parent=parent2)
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "parent",
                "page_size": 1,
                "page_number": 2,
            }
        )
        assert len(result["groups"]) == 1
        assert len(result["groups"][0]["items"]) == 1
        assert result["groups"][0]["items"][0]["id"] not in (
            parent1.id,
            parent2.id,
        )

    def test_group_parent_pages_no_parent_previous_page_without_parent(
        self, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        # On the second page, the previous page ended with a machine
        # without a parent.
        admin, session = factory.make_admin_with_session()
        factory.make_Machine(owner=admin)
        factory.make_Machine(owner=admin)
        factory.make_Machine(owner=admin)
        factory.make_Machine(owner=admin)
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "parent",
                "page_size": 2,
                "page_number": 2,
            }
        )
        assert len(result["groups"]) == 1
        assert len(result["groups"][0]["items"]) == 2

    def test_group_zone(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        zones = sorted(
            [factory.make_Zone() for _ in range(2)], key=attrgetter("name")
        )
        factory.make_Node(
            owner=user,
            zone=zones[1],
        )
        factory.make_Node(
            owner=user,
            zone=zones[0],
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "zone",
            }
        )
        assert result["groups"][0]["name"] == zones[0].name
        assert result["groups"][1]["name"] == zones[1].name

    def test_group_collapse_static(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.ALLOCATED,
        )
        factory.make_Node(
            owner=user,
            status=NODE_STATUS.NEW,
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        result = handler.list_ids(
            {
                "group_key": "status",
                "group_collapsed": ["new"],
            }
        )
        assert result["groups"][0]["name"] == "New"
        assert result["groups"][1]["name"] == "Allocated"
        assert result["groups"][0]["collapsed"]
        assert not result["groups"][1]["collapsed"]

    def test_filter_dynamic_options(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")

        with transaction.atomic():
            user, session = factory.make_User_with_session()
            tag = factory.make_Tag()
            fabric = factory.make_Fabric(class_type="test-fabric-class")
            factory.make_usable_boot_resource(architecture="amd64/generic")
            node = factory.make_Machine_with_Interface_on_Subnet(
                architecture="amd64/generic",
                bmc=factory.make_Pod(),
                owner=user,
                fabric=fabric,
                interface_speed=1000,
            )
            node.tags.add(tag)

        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        for filter_grp in handler.filter_groups({}):
            key = filter_grp["key"]
            if filter_grp["dynamic"] and not key.startswith("not_"):
                opts = handler.filter_options({"group_key": key})
                if filter_grp["type"] == "list[str]":
                    filter = {key: [k["key"] for k in opts]}
                else:
                    filter = {key: opts[0]["key"]}
                handler.list_ids({"filter": filter})

    def test_unsubscribe_prevents_further_updates_for_pk(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        admin, session = factory.make_admin_with_session()
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        node = factory.make_Node()
        handler.list_ids({})
        listen_result = handler.on_listen("machine", "update", node.system_id)
        assert listen_result is not None
        handler.unsubscribe({"system_ids": [node.system_id]})
        assert handler.on_listen("machine", "update", node.system_id) is None
        list_result = handler.list_ids({})
        assert len(list_result["groups"][0]["items"]) == 1

    def test_unsubscribe_returns_serializable_type(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        admin, session = factory.make_admin_with_session()
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        nodes = [factory.make_Node() for _ in range(3)]
        handler.list_ids({})
        resp = handler.unsubscribe(
            {"system_ids": [node.system_id for node in nodes]}
        )
        assert isinstance(resp, list)

    def test_read_an_unsubscribed_object_subscribes(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        admin, session = factory.make_admin_with_session()
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        handler.list_ids({})
        assert (
            handler.on_listen("machine", "update", node1.system_id) is not None
        )
        assert (
            handler.on_listen("machine", "update", node2.system_id) is not None
        )
        handler.unsubscribe({"system_ids": [node2.system_id]})
        assert (
            handler.on_listen("machine", "update", node1.system_id) is not None
        )
        assert handler.on_listen("machine", "update", node2.system_id) is None
        assert handler.get({"system_id": node2.system_id}) is not None
        assert (
            handler.on_listen("machine", "update", node2.system_id) is not None
        )

    def test_list_an_unsubscribed_object_subscribes(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        admin, session = factory.make_admin_with_session()
        handler = MachineHandler(
            admin, {}, None, session_id=session.session_key
        )
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        handler.list_ids({})
        assert (
            handler.on_listen("machine", "update", node1.system_id) is not None
        )
        assert (
            handler.on_listen("machine", "update", node2.system_id) is not None
        )
        handler.unsubscribe({"system_ids": [node1.system_id]})
        assert (
            handler.on_listen("machine", "update", node2.system_id) is not None
        )
        assert handler.on_listen("machine", "update", node1.system_id) is None
        list_result = handler.list_ids({})
        assert len(list_result["groups"][0]["items"]) == 2
        assert (
            handler.on_listen("machine", "update", node1.system_id) is not None
        )
        assert (
            handler.on_listen("machine", "update", node2.system_id) is not None
        )


@pytest.mark.allow_transactions
@pytest.mark.usefixtures("maasapiserver")
class TestMachineHandlerWithMaasApiServer:
    def test_list_no_power_params_certificate(self):
        user, session = factory.make_User_with_session()
        sample_cert = get_sample_cert()
        factory.make_Node(
            power_type="lxd",
            power_parameters={
                "power_address": "lxd.maas",
                "certificate": sample_cert.certificate_pem(),
                "key": sample_cert.private_key_pem(),
            },
        )
        transaction.commit()
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        list_results = handler.list({})
        [node_info] = list_results["groups"][0]["items"]
        assert "certificate" not in node_info

    def test_list(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)

        factory.make_ScriptResult(
            script_set=factory.make_ScriptSet(node=node),
            status=SCRIPT_STATUS.PASSED,
        )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        factory.make_PhysicalBlockDevice(node=node)

        assert node.id not in handler._script_results.keys()
        transaction.commit()
        list_results = handler.list({})
        list_items = list_results["groups"][0]["items"]
        assert len(handler._script_results) == 0

        assert "commissioning_status" not in list_items[0]
        assert "commissioning_start_time" not in list_items[0]
        assert "cpu_speed" not in list_items[0]
        assert list_items == [
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )
        ]

    def test_list_scriptresults(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        node = factory.make_Node(status=NODE_STATUS.ALLOCATED, owner=user)
        factory.make_ScriptResult(
            script=factory.make_Script(hardware_type=HARDWARE_TYPE.STORAGE),
            script_set=factory.make_ScriptSet(
                result_type=SCRIPT_TYPE.TESTING, node=node
            ),
            status=SCRIPT_STATUS.PASSED,
        )
        # This one should be ignored as it's not of type RESULT_TYPE.TESTING
        factory.make_ScriptResult(
            script=factory.make_Script(hardware_type=HARDWARE_TYPE.NETWORK),
            script_set=factory.make_ScriptSet(
                result_type=SCRIPT_TYPE.COMMISSIONING, node=node
            ),
            status=SCRIPT_STATUS.FAILED,
        )
        # This one should be ignored as it's suppressed
        factory.make_ScriptResult(
            script=factory.make_Script(hardware_type=HARDWARE_TYPE.CPU),
            script_set=factory.make_ScriptSet(
                result_type=SCRIPT_TYPE.TESTING, node=node
            ),
            status=SCRIPT_STATUS.PASSED,
            suppressed=True,
        )

        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        factory.make_PhysicalBlockDevice(node=node)
        transaction.commit()
        list_results = handler.list({})
        assert len(list_results["groups"][0]["items"]) == 1
        node_response = list_results["groups"][0]["items"][0]
        assert node_response["storage_test_status"] == {
            "status": 2,
            "pending": -1,
            "running": -1,
            "passed": -1,
            "failed": -1,
        }
        assert node_response["network_test_status"] == {
            "status": -1,
            "pending": -1,
            "running": -1,
            "passed": -1,
            "failed": -1,
        }
        assert node_response["cpu_test_status"] == {
            "status": -1,
            "pending": -1,
            "running": -1,
            "passed": -1,
            "failed": -1,
        }

    def test_list_ignores_devices(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        owner, session = factory.make_User_with_session()
        handler = MachineHandler(
            owner, {}, None, session_id=session.session_key
        )
        # Create a device.
        factory.make_Node(owner=owner, node_type=NODE_TYPE.DEVICE)
        node = factory.make_Node(owner=owner)
        transaction.commit()
        list_results = handler.list({})
        assert list_results["groups"][0]["items"] == [
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )
        ]

    def test_list_ephemeral_deployment(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        owner, session = factory.make_User_with_session()
        handler = MachineHandler(
            owner, {}, None, session_id=session.session_key
        )
        node = factory.make_Node(
            owner=owner,
            node_type=NODE_TYPE.MACHINE,
            status=NODE_STATUS.READY,
            ephemeral_deploy=True,
        )
        transaction.commit()
        list_results = handler.list({})
        assert list_results["groups"][0]["items"] == [
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )
        ]

    def test_list_ephemeral_deployment_when_diskless(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        owner, session = factory.make_User_with_session()
        handler = MachineHandler(
            owner, {}, None, session_id=session.session_key
        )
        node = factory.make_Node(
            owner=owner,
            node_type=NODE_TYPE.MACHINE,
            status=NODE_STATUS.READY,
            with_boot_disk=False,
        )
        transaction.commit()
        list_results = handler.list({})
        assert list_results["groups"][0]["items"] == [
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )
        ]

    def test_list_includes_pod_details_when_available(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        pod = factory.make_Pod()
        node = factory.make_Node(owner=user, bmc=pod)
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        transaction.commit()
        list_results = handler.list({})
        assert list_results["groups"][0]["items"] == [
            TestMachineHandlerUtils.dehydrate_node(
                node, handler, for_list=True
            )
        ]

    def test_sort_alias(self, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        user, session = factory.make_User_with_session()
        fabrics = [factory.make_Fabric() for _ in range(2)]
        subnets = [factory.make_Subnet(fabric=fabrics[i]) for i in range(2)]
        statuses = [NODE_STATUS.ALLOCATED, NODE_STATUS.FAILED_COMMISSIONING]
        nodes = [
            factory.make_Machine_with_Interface_on_Subnet(
                owner=user,
                status=statuses[idx],
                hostname=f"node{idx}-{factory.make_string(10)}",
                subnet=subnets[idx],
            )
            for idx in range(2)
        ]
        for i, node in enumerate(nodes):
            for _ in range(i):
                factory.make_PhysicalBlockDevice(
                    node=node, size=MIN_BOOT_PARTITION_SIZE
                )
        handler = MachineHandler(
            user, {}, None, session_id=session.session_key
        )
        transaction.commit()
        for key in (
            "storage",
            "physical_disk_count",
            "fqdn",
            "pxe_mac",
            "simple_status",
        ):
            result = handler.list(
                {
                    "sort_key": key,
                    "sort_direction": "descending",
                }
            )
            items = result["groups"][0]["items"]
            assert result["groups"][0]["count"] == 2
            assert items[1][key] < items[0][key], key

        # fabric_name is not the name of the field
        result = handler.list(
            {
                "sort_key": "fabric_name",
                "sort_direction": "descending",
            }
        )
        items = result["groups"][0]["items"]
        assert result["groups"][0]["count"] == 2
        assert (
            items[1]["vlan"]["fabric_name"] < items[0]["vlan"]["fabric_name"]
        ), "fabric"

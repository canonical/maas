# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maascommon.openfga.async_client import OpenFGAClient
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from tests.e2e.env import skip_if_integration_disabled


@pytest.mark.asyncio
@skip_if_integration_disabled()
class TestIntegrationConfigurationsService:
    @pytest.mark.allow_transactions
    @pytest.mark.usefixtures("db_connection")
    async def test_get(
        self, openfga_server, openfga_socket_path, db_connection, db
    ):
        services = await ServiceCollectionV3.produce(
            Context(connection=db_connection), cache=CacheForServices()
        )

        # Create pool:1, pool:2 and pool:3. pool:1 is the default and already exists
        for i in range(1, 4):
            await services.openfga_tuples.create(
                OpenFGATupleBuilder.build_pool(str(i))
            )

        # team A can edit and view everything
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_machines(group_id="teamA")
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_global_entities(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_controllers(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_identities(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_configurations(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_boot_entities(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_notifications(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_license_keys(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_view_devices(group_id="teamA")
        )

        # alice belongs to group team A
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_user_member_group(
                user_id="alice", group_id="teamA"
            )
        )

        # team B can_edit_machines and can_view_machines in pool:0
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_machines_in_pool(
                group_id="teamB", pool_id="0"
            )
        )
        # bob belongs to group team B
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_user_member_group(
                user_id="bob", group_id="teamB"
            )
        )

        # team C can_view_machines in pool:0
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_deploy_machines_in_pool(
                group_id="teamC", pool_id="0"
            )
        )
        # carl belongs to group team C
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_user_member_group(
                user_id="carl", group_id="teamC"
            )
        )

        # team D can_view_machines in pool:0
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_view_available_machines_in_pool(
                group_id="teamD", pool_id="0"
            )
        )
        # carl belongs to group team C
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_user_member_group(
                user_id="dingo", group_id="teamD"
            )
        )

        await db_connection.commit()

        client = OpenFGAClient(str(openfga_socket_path))
        # alice should have all permissions on pool1 because of teamA's system rights
        for i in range(0, 3):
            assert (
                await client.can_edit_machines_in_pool(
                    user_id="alice", pool_id=str(i)
                )
            ) is True
            assert (
                await client.can_view_machines_in_pool(
                    user_id="alice", pool_id=str(i)
                )
            ) is True
            assert (
                await client.can_view_available_machines_in_pool(
                    user_id="alice", pool_id=str(i)
                )
            ) is True
            assert (
                await client.can_deploy_machines_in_pool(
                    user_id="alice", pool_id=str(i)
                )
            ) is True

        assert (await client.can_edit_machines(user_id="alice")) is True
        assert (await client.can_edit_global_entities(user_id="alice")) is True
        assert (await client.can_view_global_entities(user_id="alice")) is True
        assert (await client.can_edit_controllers(user_id="alice")) is True
        assert (await client.can_view_controllers(user_id="alice")) is True
        assert (await client.can_edit_identities(user_id="alice")) is True
        assert (await client.can_view_identities(user_id="alice")) is True
        assert (await client.can_edit_configurations(user_id="alice")) is True
        assert (await client.can_view_configurations(user_id="alice")) is True
        assert (await client.can_edit_notifications(user_id="alice")) is True
        assert (await client.can_view_notifications(user_id="alice")) is True
        assert (await client.can_edit_boot_entities(user_id="alice")) is True
        assert (await client.can_view_boot_entities(user_id="alice")) is True
        assert (await client.can_view_license_keys(user_id="alice")) is True
        assert (await client.can_edit_license_keys(user_id="alice")) is True
        assert (await client.can_view_devices(user_id="alice")) is True

        # bob should just have edit,view and deploy permissions on pool1 because of teamB's rights
        assert (
            await client.can_edit_machines_in_pool(user_id="bob", pool_id="0")
        ) is True
        assert (
            await client.can_view_machines_in_pool(user_id="bob", pool_id="0")
        ) is True
        assert (
            await client.can_view_available_machines_in_pool(
                user_id="bob", pool_id="0"
            )
        ) is True
        assert (
            await client.can_deploy_machines_in_pool(
                user_id="bob", pool_id="0"
            )
        ) is True

        for i in range(1, 3):
            assert (
                await client.can_edit_machines_in_pool(
                    user_id="bob", pool_id=str(i)
                )
            ) is False
            assert (
                await client.can_view_machines_in_pool(
                    user_id="bob", pool_id=str(i)
                )
            ) is False
            assert (
                await client.can_view_available_machines_in_pool(
                    user_id="bob", pool_id=str(i)
                )
            ) is False
            assert (
                await client.can_deploy_machines_in_pool(
                    user_id="bob", pool_id=str(i)
                )
            ) is False

        assert (await client.can_edit_machines(user_id="bob")) is False
        assert (await client.can_view_global_entities(user_id="bob")) is False
        assert (await client.can_edit_global_entities(user_id="bob")) is False
        assert (await client.can_edit_identities(user_id="bob")) is False
        assert (await client.can_view_identities(user_id="bob")) is False
        assert (await client.can_edit_configurations(user_id="bob")) is False
        assert (await client.can_view_configurations(user_id="bob")) is False
        assert (await client.can_view_notifications(user_id="bob")) is False
        assert (await client.can_edit_notifications(user_id="bob")) is False
        assert (await client.can_view_boot_entities(user_id="bob")) is False
        assert (await client.can_edit_boot_entities(user_id="bob")) is False
        assert (await client.can_view_license_keys(user_id="bob")) is False
        assert (await client.can_edit_license_keys(user_id="bob")) is False
        assert (await client.can_view_devices(user_id="bob")) is False

        # carl should just have deploy permissions on pool0 because of teamC's rights
        assert (
            await client.can_edit_machines_in_pool(user_id="carl", pool_id="0")
        ) is False
        assert (
            await client.can_view_machines_in_pool(user_id="carl", pool_id="0")
        ) is False
        assert (
            await client.can_view_available_machines_in_pool(
                user_id="carl", pool_id="0"
            )
        ) is False
        assert (
            await client.can_deploy_machines_in_pool(
                user_id="carl", pool_id="0"
            )
        ) is True

        # dingo should just view permissions on pool0 because of teamD's rights
        assert (
            await client.can_edit_machines_in_pool(
                user_id="dingo", pool_id="0"
            )
        ) is False
        assert (
            await client.can_view_machines_in_pool(
                user_id="dingo", pool_id="0"
            )
        ) is False
        assert (
            await client.can_view_available_machines_in_pool(
                user_id="dingo", pool_id="0"
            )
        ) is True
        assert (
            await client.can_deploy_machines_in_pool(
                user_id="dingo", pool_id="0"
            )
        ) is False

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
            await services.openfga_tuples.upsert(
                OpenFGATupleBuilder.build_pool(str(i))
            )

        # group 1000 can edit and view everything
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_machines(group_id=1000)
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_global_entities(
                group_id=1000
            )
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_controllers(group_id=1000)
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_identities(group_id=1000)
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_configurations(
                group_id=1000
            )
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_boot_entities(
                group_id=1000
            )
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_notifications(
                group_id=1000
            )
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_license_keys(
                group_id=1000
            )
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_view_devices(group_id=1000)
        )
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_view_dnsrecords(group_id=1000)
        )

        # user 1000 belongs to group 1000
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_user_member_group(
                user_id=1000, group_id=1000
            )
        )

        # group 2000 can_edit_machines and can_view_machines in pool:0
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_edit_machines_in_pool(
                group_id=2000, pool_id="0"
            )
        )
        # user 2000 belongs to group 2000
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_user_member_group(
                user_id=2000, group_id=2000
            )
        )

        # group 3000 can_view_machines in pool:0
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_deploy_machines_in_pool(
                group_id=3000, pool_id="0"
            )
        )
        # user 3000 belongs to group 3000
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_user_member_group(
                user_id=3000, group_id=3000
            )
        )

        # group 4000 can_view_machines in pool:0
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_group_can_view_available_machines_in_pool(
                group_id=4000, pool_id="0"
            )
        )
        # user 4000 belongs to group 4000
        await services.openfga_tuples.upsert(
            OpenFGATupleBuilder.build_user_member_group(
                user_id=4000, group_id=4000
            )
        )

        await db_connection.commit()

        client = OpenFGAClient(str(openfga_socket_path))
        # user 1000 should have all permissions on pool1 because of group 1000's system rights
        for i in range(0, 3):
            assert (
                await client.can_edit_machines_in_pool(
                    user_id=1000, pool_id=str(i)
                )
            ) is True
            assert (
                await client.can_view_machines_in_pool(
                    user_id=1000, pool_id=str(i)
                )
            ) is True
            assert (
                await client.can_view_available_machines_in_pool(
                    user_id=1000, pool_id=str(i)
                )
            ) is True
            assert (
                await client.can_deploy_machines_in_pool(
                    user_id=1000, pool_id=str(i)
                )
            ) is True

        assert (await client.can_edit_machines(user_id=1000)) is True
        assert (await client.can_edit_global_entities(user_id=1000)) is True
        assert (await client.can_view_global_entities(user_id=1000)) is True
        assert (await client.can_edit_controllers(user_id=1000)) is True
        assert (await client.can_view_controllers(user_id=1000)) is True
        assert (await client.can_edit_identities(user_id=1000)) is True
        assert (await client.can_view_identities(user_id=1000)) is True
        assert (await client.can_edit_configurations(user_id=1000)) is True
        assert (await client.can_view_configurations(user_id=1000)) is True
        assert (await client.can_edit_notifications(user_id=1000)) is True
        assert (await client.can_view_notifications(user_id=1000)) is True
        assert (await client.can_edit_boot_entities(user_id=1000)) is True
        assert (await client.can_view_boot_entities(user_id=1000)) is True
        assert (await client.can_view_license_keys(user_id=1000)) is True
        assert (await client.can_edit_license_keys(user_id=1000)) is True
        assert (await client.can_view_devices(user_id=1000)) is True
        assert (await client.can_view_dnsrecords(user_id=1000)) is True

        # user 2000 should just have edit,view and deploy permissions on pool1 because of group 2000's rights
        assert (
            await client.can_edit_machines_in_pool(user_id=2000, pool_id="0")
        ) is True
        assert (
            await client.can_view_machines_in_pool(user_id=2000, pool_id="0")
        ) is True
        assert (
            await client.can_view_available_machines_in_pool(
                user_id=2000, pool_id="0"
            )
        ) is True
        assert (
            await client.can_deploy_machines_in_pool(user_id=2000, pool_id="0")
        ) is True

        for i in range(1, 3):
            assert (
                await client.can_edit_machines_in_pool(
                    user_id=2000, pool_id=str(i)
                )
            ) is False
            assert (
                await client.can_view_machines_in_pool(
                    user_id=2000, pool_id=str(i)
                )
            ) is False
            assert (
                await client.can_view_available_machines_in_pool(
                    user_id=2000, pool_id=str(i)
                )
            ) is False
            assert (
                await client.can_deploy_machines_in_pool(
                    user_id=2000, pool_id=str(i)
                )
            ) is False

        assert (await client.can_edit_machines(user_id=2000)) is False
        assert (await client.can_view_global_entities(user_id=2000)) is False
        assert (await client.can_edit_global_entities(user_id=2000)) is False
        assert (await client.can_edit_identities(user_id=2000)) is False
        assert (await client.can_view_identities(user_id=2000)) is False
        assert (await client.can_edit_configurations(user_id=2000)) is False
        assert (await client.can_view_configurations(user_id=2000)) is False
        assert (await client.can_view_notifications(user_id=2000)) is False
        assert (await client.can_edit_notifications(user_id=2000)) is False
        assert (await client.can_view_boot_entities(user_id=2000)) is False
        assert (await client.can_edit_boot_entities(user_id=2000)) is False
        assert (await client.can_view_license_keys(user_id=2000)) is False
        assert (await client.can_edit_license_keys(user_id=2000)) is False
        assert (await client.can_view_devices(user_id=2000)) is False
        assert (await client.can_view_dnsrecords(user_id=2000)) is False

        # user 3000 should just have deploy permissions on pool0 because of group 3000's rights
        assert (
            await client.can_edit_machines_in_pool(user_id=3000, pool_id="0")
        ) is False
        assert (
            await client.can_view_machines_in_pool(user_id=3000, pool_id="0")
        ) is False
        assert (
            await client.can_view_available_machines_in_pool(
                user_id=3000, pool_id="0"
            )
        ) is False
        assert (
            await client.can_deploy_machines_in_pool(user_id=3000, pool_id="0")
        ) is True

        # user 4000 should just view permissions on pool0 because of group 4000's rights
        assert (
            await client.can_edit_machines_in_pool(user_id=4000, pool_id="0")
        ) is False
        assert (
            await client.can_view_machines_in_pool(user_id=4000, pool_id="0")
        ) is False
        assert (
            await client.can_view_available_machines_in_pool(
                user_id=4000, pool_id="0"
            )
        ) is True
        assert (
            await client.can_deploy_machines_in_pool(user_id=4000, pool_id="0")
        ) is False

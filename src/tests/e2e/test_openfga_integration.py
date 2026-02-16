# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
import os
import subprocess
import time

import pytest
import yaml

from maascommon.openfga.client.client import OpenFGAClient
from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.services import CacheForServices, ServiceCollectionV3
from tests.e2e.env import skip_if_integration_disabled


@pytest.fixture
def project_root_path(request):
    return request.config.rootpath


@pytest.fixture
def openfga_socket_path(tmpdir):
    return tmpdir / "openfga-http.sock"


@pytest.fixture
def openfga_server(tmpdir, project_root_path, openfga_socket_path, db):
    """Fixture to start the OpenFGA server as a subprocess for testing. After the test is done, it ensures that the server process is terminated."""
    binary_path = project_root_path / "src/maasopenfga/build/maas-openfga"

    # Set the environment variable for the OpenFGA server to use the socket path in the temporary directory
    env = os.environ.copy()
    env["MAAS_OPENFGA_HTTP_SOCKET_PATH"] = str(openfga_socket_path)

    regiond_conf = {
        "database_host": db.config.host,
        "database_name": db.config.name,
        "database_user": "ubuntu",
    }

    # Write the regiond configuration to a file in the temporary directory
    with open(tmpdir / "regiond.conf", "w") as f:
        f.write(yaml.dump(regiond_conf))

    env["SNAP_DATA"] = str(tmpdir)

    pid = subprocess.Popen(binary_path, env=env)

    timeout = timedelta(seconds=30)
    start_time = time.monotonic()
    while True:
        if time.monotonic() - start_time > timeout.total_seconds():
            pid.terminate()
            raise TimeoutError(
                "OpenFGA server did not start within the expected time."
            )
        if not openfga_socket_path.exists():
            time.sleep(0.5)
        else:
            break
    yield pid
    pid.terminate()


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

        # Create pool:0, pool:1 and pool:2
        for i in range(0, 3):
            await services.openfga_tuples.create(
                OpenFGATupleBuilder.build_pool(str(i))
            )

        # team A can edit and view everything
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_pools(group_id="teamA")
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_global_entities(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_permissions(
                group_id="teamA"
            )
        )
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_configurations(
                group_id="teamA"
            )
        )

        # alice belongs to group team A
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_user_member_group(
                user_id="alice", group_id="teamA"
            )
        )

        # team B can_edit_machines and can_view_machines in pool:0
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_group_can_edit_machines(
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
            OpenFGATupleBuilder.build_group_can_deploy_machines(
                group_id="teamC", pool_id="0"
            )
        )
        # bob belongs to group team B
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_user_member_group(
                user_id="carl", group_id="teamC"
            )
        )

        await db_connection.commit()

        client = OpenFGAClient(str(openfga_socket_path))
        # alice should have all permissions on pool1 because of teamA's system rights
        assert (await client.can_edit_pools(user_id="alice")) is True
        assert (await client.can_view_pools(user_id="alice")) is True

        for i in range(0, 3):
            assert (
                await client.can_edit_machines(user_id="alice", pool_id=str(i))
            ) is True
            assert (
                await client.can_view_machines(user_id="alice", pool_id=str(i))
            ) is True
            assert (
                await client.can_deploy_machines(
                    user_id="alice", pool_id=str(i)
                )
            ) is True

        assert (await client.can_view_global_entities(user_id="alice")) is True
        assert (await client.can_edit_global_entities(user_id="alice")) is True
        assert (await client.can_view_permissions(user_id="alice")) is True
        assert (await client.can_edit_permissions(user_id="alice")) is True
        assert (await client.can_view_configurations(user_id="alice")) is True
        assert (await client.can_edit_configurations(user_id="alice")) is True

        # bob should just have edit,view and deploy permissions on pool1 because of teamB's rights
        assert (await client.can_edit_pools(user_id="bob")) is False
        assert (await client.can_view_pools(user_id="bob")) is False

        assert (
            await client.can_edit_machines(user_id="bob", pool_id="0")
        ) is True
        assert (
            await client.can_view_machines(user_id="bob", pool_id="0")
        ) is True
        assert (
            await client.can_deploy_machines(user_id="bob", pool_id="0")
        ) is True

        for i in range(1, 3):
            assert (
                await client.can_edit_machines(user_id="bob", pool_id=str(i))
            ) is False
            assert (
                await client.can_view_machines(user_id="bob", pool_id=str(i))
            ) is False
            assert (
                await client.can_deploy_machines(user_id="bob", pool_id=str(i))
            ) is False

        assert (await client.can_view_global_entities(user_id="bob")) is False
        assert (await client.can_edit_global_entities(user_id="bob")) is False
        assert (await client.can_view_permissions(user_id="bob")) is False
        assert (await client.can_edit_permissions(user_id="bob")) is False
        assert (await client.can_view_configurations(user_id="bob")) is False
        assert (await client.can_edit_configurations(user_id="bob")) is False

        # carl should just have deploy and view permissions on pool0 because of teamC's rights
        assert (
            await client.can_edit_machines(user_id="carl", pool_id="0")
        ) is False
        assert (
            await client.can_view_machines(user_id="carl", pool_id="0")
        ) is True
        assert (
            await client.can_deploy_machines(user_id="carl", pool_id="0")
        ) is True

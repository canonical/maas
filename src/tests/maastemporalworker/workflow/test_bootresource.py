#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib
from itertools import islice, repeat
import os
from pathlib import Path
import shutil
from unittest.mock import Mock

import pytest
from temporalio.testing import ActivityEnvironment

from maasservicelayer.db import Database
from maasservicelayer.services import CacheForServices
from maastemporalworker.workflow.api_client import MAASAPIClient
from maastemporalworker.workflow.bootresource import (
    BootResourcesActivity,
    SpaceRequirementParam,
)

FILE_SIZE = 50


@pytest.fixture
def controller(factory, mocker):
    mocker.patch("maasserver.utils.orm.post_commit_hooks")
    mocker.patch("maasserver.utils.orm.post_commit_do")
    controller = factory.make_RegionRackController()
    yield controller


@pytest.fixture
def maas_data_dir(mocker, tmpdir):
    mocker.patch.dict(os.environ, {"MAAS_DATA": str(tmpdir)})
    yield tmpdir


@pytest.fixture
def image_store_dir(maas_data_dir, mocker):
    store = Path(maas_data_dir) / "image-storage"
    store.mkdir()
    mock_disk_usage = mocker.patch("shutil.disk_usage")
    mock_disk_usage.return_value = (0, 0, 101)  # only care about 'free'
    yield store
    shutil.rmtree(store)


@pytest.fixture
def boot_activities(mocker, controller):
    act = BootResourcesActivity(Mock(Database), CacheForServices())
    act.apiclient = Mock(MAASAPIClient)
    act.region_id = controller.system_id
    yield act


@pytest.fixture
def a_file(image_store_dir):
    content = bytes(b"".join(islice(repeat(b"\x01"), FILE_SIZE)))
    sha256 = hashlib.sha256()
    sha256.update(content)
    file = image_store_dir / f"{str(sha256.hexdigest())}"
    with file.open("wb") as f:
        f.write(content)
    yield file


@pytest.mark.usefixtures("maasdb")
class TestCheckDiskSpace:
    async def test_check_disk_space_total(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        param = SpaceRequirementParam(total_resources_size=100)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert ok

    async def test_check_disk_space_total_has_space(
        self, boot_activities, image_store_dir, a_file
    ):
        env = ActivityEnvironment()
        param = SpaceRequirementParam(total_resources_size=70)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert ok

    async def test_check_disk_space_total_full(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        param = SpaceRequirementParam(total_resources_size=120)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert not ok

    async def test_check_disk_space_min_free_space(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        param = SpaceRequirementParam(min_free_space=50)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert ok

    async def test_check_disk_space_min_free_space_full(
        self, boot_activities, image_store_dir
    ):
        env = ActivityEnvironment()
        param = SpaceRequirementParam(min_free_space=500)
        ok = await env.run(boot_activities.check_disk_space, param)
        assert not ok

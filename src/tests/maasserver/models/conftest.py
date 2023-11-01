# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random

import pytest

from maasserver.models.bootresource import BootResource
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.models.node import RegionController


@pytest.fixture
def bootresfile_size() -> int:
    file_size = random.randint(1, 1024)
    yield file_size


@pytest.fixture
def region_cluster(factory) -> list[RegionController]:
    cluster = [factory.make_RegionController() for _ in range(3)]
    yield cluster


@pytest.fixture
def bootres(factory) -> BootResource:
    resource = factory.make_BootResource()
    yield resource


@pytest.fixture
def bootres_set(factory, bootres) -> BootResourceSet:
    resource_set = factory.make_BootResourceSet(bootres)
    yield resource_set


@pytest.fixture
def bootres_file(factory, bootres_set, bootresfile_size) -> BootResourceFile:
    rfile = factory.make_BootResourceFile(bootres_set, size=bootresfile_size)
    yield rfile


@pytest.fixture
def bootres_file_shared(
    factory, bootres_set, bootres_file
) -> BootResourceFile:
    rfile = factory.make_BootResourceFile(
        bootres_set,
        sha256=bootres_file.sha256,
        size=bootres_file.size,
    )
    yield rfile


@pytest.fixture
def bootres_file_synced(
    factory, bootres_set, bootresfile_size, region_cluster
) -> BootResourceFile:
    sync_status = [(region, -1) for region in region_cluster]
    rfile = factory.make_BootResourceFile(
        bootres_set, size=bootresfile_size, synced=sync_status
    )
    yield rfile


@pytest.fixture
def bootres_file_partial_sync(
    factory, bootres_set, bootresfile_size, region_cluster
) -> BootResourceFile:
    sync_status = [
        (region, random.randint(0, bootresfile_size - 1))
        for region in region_cluster[1:]
    ]
    sync_status.append((region_cluster[0], -1))
    rfile = factory.make_BootResourceFile(
        bootres_set, size=bootresfile_size, synced=sync_status
    )
    yield rfile

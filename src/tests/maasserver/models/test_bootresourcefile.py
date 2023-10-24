import random

import pytest


@pytest.mark.usefixtures("maasdb")
class TestBootResourceFile:
    def test_get_sync_source(self, factory):
        file_size = random.randint(1, 1024)
        sync_status = [
            (factory.make_RegionController(), random.randint(0, file_size - 1))
            for _ in range(3)
        ]
        synced_region = factory.make_RegionController()
        sync_status += [(synced_region, file_size)]
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        rfile = factory.make_BootResourceFile(
            resource_set, size=file_size, synced=sync_status
        )

        assert rfile.has_complete_copy
        assert rfile.get_regions_with_complete_copy() == [
            synced_region.system_id
        ]

    def test_get_sync_source_not_synced(self, factory):
        file_size = random.randint(1, 1024)
        sync_status = [
            (factory.make_RegionController(), random.randint(0, file_size - 1))
            for _ in range(3)
        ]
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        rfile = factory.make_BootResourceFile(
            resource_set, size=file_size, synced=sync_status
        )

        assert not rfile.has_complete_copy
        assert rfile.get_regions_with_complete_copy() == []

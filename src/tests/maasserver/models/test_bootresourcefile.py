# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import string

import pytest

from maasserver.models import bootresourcefile as brf
from maasserver.models.bootresource import BootResource
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.testing.factory import factory


@pytest.fixture
def exec_workflow_mock(mocker):
    yield mocker.patch.object(brf, "execute_workflow")


@pytest.mark.usefixtures("maasdb")
class TestBootResourceFile:
    def test_get_sync_source(self, bootres_file_partial_sync, region_cluster):
        assert bootres_file_partial_sync.has_complete_copy
        assert bootres_file_partial_sync.get_regions_with_complete_copy() == [
            region_cluster[0].system_id
        ]

    def test_get_sync_source_not_synced(self, bootres_file):
        assert not bootres_file.has_complete_copy
        assert bootres_file.get_regions_with_complete_copy() == []


@pytest.mark.usefixtures("maasdb")
class TestFileStore:
    def test_filestore_remove_file(self, exec_workflow_mock, bootres_file):
        BootResourceFile.objects.filestore_remove_file(bootres_file)
        exec_workflow_mock.assert_called()
        workflow, wid, _ = exec_workflow_mock.call_args.args
        assert workflow == "delete-bootresource"
        assert wid == f"bootresource-del:{bootres_file.id}"

    def test_filestore_remove_file_shared(
        self, exec_workflow_mock, bootres_file, bootres_file_shared
    ):
        BootResourceFile.objects.filestore_remove_file(bootres_file)
        exec_workflow_mock.assert_not_called()
        assert bootres_file.sha256 == bootres_file_shared.sha256

    def test_filestore_remove_files(self, exec_workflow_mock, bootres_file):
        qs = BootResourceFile.objects.filter(id=bootres_file.id)
        BootResourceFile.objects.filestore_remove_files(qs)
        exec_workflow_mock.assert_called()
        workflow = exec_workflow_mock.call_args.args[0]
        param = exec_workflow_mock.call_args.kwargs["param"]
        assert workflow == "delete-bootresource"
        assert param.files[0].sha256 == bootres_file.sha256
        assert param.files[0].filename_on_disk == bootres_file.filename_on_disk

    def test_filestore_remove_files_shared(
        self, exec_workflow_mock, bootres_file, bootres_file_shared
    ):
        qs = BootResourceFile.objects.filter(id=bootres_file.id)
        BootResourceFile.objects.filestore_remove_files(qs)
        exec_workflow_mock.assert_not_called()
        assert bootres_file.sha256 == bootres_file_shared.sha256

    def test_filestore_remove_set(
        self, exec_workflow_mock, bootres_set, bootres_file
    ):
        BootResourceFile.objects.filestore_remove_set(bootres_set)
        exec_workflow_mock.assert_called()
        workflow = exec_workflow_mock.call_args.args[0]
        param = exec_workflow_mock.call_args.kwargs["param"]
        assert workflow == "delete-bootresource"
        assert param.files[0].sha256 == bootres_file.sha256
        assert param.files[0].filename_on_disk == bootres_file.filename_on_disk

    def test_filestore_remove_sets(
        self, exec_workflow_mock, bootres_set, bootres_file
    ):
        qset = BootResourceSet.objects.filter(id=bootres_set.id)
        BootResourceFile.objects.filestore_remove_sets(qset)
        exec_workflow_mock.assert_called()
        workflow = exec_workflow_mock.call_args.args[0]
        param = exec_workflow_mock.call_args.kwargs["param"]
        assert workflow == "delete-bootresource"
        assert param.files[0].sha256 == bootres_file.sha256
        assert param.files[0].filename_on_disk == bootres_file.filename_on_disk

    def test_filestore_remove_sets_shared(
        self,
        exec_workflow_mock,
        bootres_set,
        bootres_file,
        bootres_file_shared,
    ):
        assert bootres_file.sha256 == bootres_file_shared.sha256
        qset = BootResourceSet.objects.filter(id=bootres_set.id)
        BootResourceFile.objects.filestore_remove_sets(qset)
        exec_workflow_mock.assert_not_called()

    def test_filestore_remove_resource(
        self, exec_workflow_mock, bootres, bootres_file
    ):
        BootResourceFile.objects.filestore_remove_resource(bootres)
        exec_workflow_mock.assert_called()
        workflow = exec_workflow_mock.call_args.args[0]
        param = exec_workflow_mock.call_args.kwargs["param"]
        assert workflow == "delete-bootresource"
        assert param.files[0].sha256 == bootres_file.sha256
        assert param.files[0].filename_on_disk == bootres_file.filename_on_disk

    def test_filestore_remove_resources(
        self, exec_workflow_mock, bootres, bootres_file
    ):
        qset = BootResource.objects.filter(id=bootres.id)
        BootResourceFile.objects.filestore_remove_resources(qset)
        exec_workflow_mock.assert_called()
        workflow = exec_workflow_mock.call_args.args[0]
        param = exec_workflow_mock.call_args.kwargs["param"]
        assert workflow == "delete-bootresource"
        assert param.files[0].sha256 == bootres_file.sha256
        assert param.files[0].filename_on_disk == bootres_file.filename_on_disk

    def test_filestore_remove_resources_shared(
        self,
        exec_workflow_mock,
        bootres,
        bootres_file,
        bootres_file_shared,
    ):
        assert bootres_file.sha256 == bootres_file_shared.sha256
        qset = BootResource.objects.filter(id=bootres.id)
        BootResourceFile.objects.filestore_remove_resources(qset)
        exec_workflow_mock.assert_not_called()

    def test_filestore_calculate_filename_on_disk_with_collision(
        self,
        bootres_set,
        bootres_file,
    ):
        # This test creates 2 bootresource files.
        # The first one has filename_on_disk with len 7.
        # The second one has the same first 7 chars of bootres_file and then the 8th is different.
        other_bootres_file_sha = (
            bootres_file.sha256[:7]
            +
            # ensure the collision is only on the first 7 chars!
            factory.make_hex_string(
                1, choices=string.hexdigits.replace(bootres_file.sha256[7], "")
            )
            + factory.make_hex_string(55)
        )
        factory.make_BootResourceFile(
            bootres_set,
            sha256=other_bootres_file_sha,
            filename_on_disk=other_bootres_file_sha[:8],
        )

        new_sha_with_collision = (
            bootres_file.sha256[:7]
            +
            # ensure the collision is only on the first 7 chars!
            factory.make_hex_string(
                1,
                choices=string.hexdigits.replace(
                    bootres_file.sha256[7], ""
                ).replace(other_bootres_file_sha[7], ""),
            )
            + factory.make_hex_string(55)
        )
        filename_on_disk_without_collision = (
            BootResourceFile.objects.calculate_filename_on_disk(
                new_sha_with_collision
            )
        )
        # The filename_on_disk is properly taking only the first 8 chars.
        assert filename_on_disk_without_collision == new_sha_with_collision[:8]

        new_sha_with_collision_longer = (
            other_bootres_file_sha[:8]
            +
            # ensure the collision is only on the first 20 chars!
            factory.make_hex_string(
                1,
                choices=string.hexdigits.replace(
                    other_bootres_file_sha[8], ""
                ),
            )
            + factory.make_hex_string(54)
        )
        filename_on_disk_without_collision_longer = (
            BootResourceFile.objects.calculate_filename_on_disk(
                new_sha_with_collision_longer
            )
        )
        assert (
            filename_on_disk_without_collision_longer
            == new_sha_with_collision_longer[:9]
        )

    def test_filestore_calculate_filename_on_disk_no_collision(
        self,
        bootres_file,
    ):
        new_sha_with_collision = factory.make_hex_string(64)
        filename_on_disk_without_collision = (
            BootResourceFile.objects.calculate_filename_on_disk(
                new_sha_with_collision
            )
        )
        assert filename_on_disk_without_collision == new_sha_with_collision[:7]

    def test_filestore_calculate_filename_on_disk_already_exists(
        self,
        bootres_file,
    ):
        filename_on_disk_without_collision = (
            BootResourceFile.objects.calculate_filename_on_disk(
                bootres_file.sha256
            )
        )
        assert (
            filename_on_disk_without_collision == bootres_file.filename_on_disk
        )

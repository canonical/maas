# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasserver.models import bootresourcefile as brf
from maasserver.models.bootresource import BootResource
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.bootresourceset import BootResourceSet


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
        assert wid == f"bootresource-del-{bootres_file.id}"

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
        params = exec_workflow_mock.call_args.kwargs["params"]
        assert workflow == "delete-bootresource"
        assert params.files[0] == bootres_file.sha256

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
        params = exec_workflow_mock.call_args.kwargs["params"]
        assert workflow == "delete-bootresource"
        assert params.files[0] == bootres_file.sha256

    def test_filestore_remove_sets(
        self, exec_workflow_mock, bootres_set, bootres_file
    ):
        qset = BootResourceSet.objects.filter(id=bootres_set.id)
        BootResourceFile.objects.filestore_remove_sets(qset)
        exec_workflow_mock.assert_called()
        workflow = exec_workflow_mock.call_args.args[0]
        params = exec_workflow_mock.call_args.kwargs["params"]
        assert workflow == "delete-bootresource"
        assert params.files[0] == bootres_file.sha256

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
        params = exec_workflow_mock.call_args.kwargs["params"]
        assert workflow == "delete-bootresource"
        assert params.files[0] == bootres_file.sha256

    def test_filestore_remove_resources(
        self, exec_workflow_mock, bootres, bootres_file
    ):
        qset = BootResource.objects.filter(id=bootres.id)
        BootResourceFile.objects.filestore_remove_resources(qset)
        exec_workflow_mock.assert_called()
        workflow = exec_workflow_mock.call_args.args[0]
        params = exec_workflow_mock.call_args.kwargs["params"]
        assert workflow == "delete-bootresource"
        assert params.files[0] == bootres_file.sha256

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

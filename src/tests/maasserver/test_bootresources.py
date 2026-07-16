# Copyright 2023-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
from pathlib import Path
import shutil

import pytest

from maasserver import bootresources
from maasserver.bootresources import initialize_image_storage
from maasserver.utils.orm import reload_object
from provisioningserver.config import ClusterConfiguration


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
def image_store_dir(maas_data_dir):
    store = Path(maas_data_dir) / "image-storage"
    store.mkdir()
    yield store
    shutil.rmtree(store)


@pytest.fixture
def tftp_root(mocker, maas_data_dir, tmpdir):
    tftp_root = Path(maas_data_dir) / "tftp_root"
    tftp_root.mkdir(parents=True)
    config = Path(tmpdir) / Path(ClusterConfiguration.DEFAULT_FILENAME).name
    with ClusterConfiguration.open_for_update(config) as cfg:
        cfg.tftp_root = str(tftp_root)
    mocker.patch.dict(os.environ, {"MAAS_CLUSTER_CONFIG": str(config)})
    yield tftp_root
    shutil.rmtree(tftp_root)


def list_files(base_path):
    return {str(path.relative_to(base_path)) for path in base_path.iterdir()}


@pytest.mark.usefixtures("maasdb")
class TestInitialiseImageStorage:
    def test_empty(self, controller, image_store_dir: Path, mocker):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        initialize_image_storage(controller)
        assert list_files(image_store_dir) == {"bootloaders"}

    def test_remove_extra_files(
        self,
        controller,
        image_store_dir: Path,
        tftp_root: Path,
        mocker,
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        custom_dir = image_store_dir / "custom"
        custom_dir.mkdir(parents=True)
        lost_found_dir = image_store_dir / "lost+found"
        lost_found_dir.mkdir(parents=True)
        extra_file = image_store_dir / "abcde"
        extra_file.write_text("some content")
        extra_dir = image_store_dir / "somedir"
        extra_dir.mkdir(parents=True)
        extra_other_file = extra_dir / "somefile"
        extra_other_file.write_text("some content")
        extra_symlink = image_store_dir / "somelink"
        extra_symlink.symlink_to(extra_other_file)

        initialize_image_storage(controller)
        assert tftp_root.exists()
        assert not extra_file.exists()
        assert not extra_dir.exists()
        assert not extra_symlink.exists()
        assert custom_dir.exists()
        assert lost_found_dir.exists()

    def test_remove_extra_symlink(
        self, controller, image_store_dir: Path, tmp_path, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        extra_dir = tmp_path / "somedir"
        extra_dir.mkdir(parents=True)
        extra_symlink = image_store_dir / "somelink"
        extra_symlink.symlink_to(extra_dir)

        initialize_image_storage(controller)
        assert not extra_symlink.exists()

    def test_missing_local_files(
        self, controller, image_store_dir: Path, factory, mocker
    ):
        mocker.patch("maasserver.utils.orm.post_commit_hooks")
        mocker.patch("maasserver.utils.orm.post_commit_do")
        resource = factory.make_usable_boot_resource()
        other = factory.make_usable_boot_resource()
        rset = resource.sets.first()
        for rfile in rset.files.all():
            lfile = rfile.local_file()
            lfile.unlink()

        initialize_image_storage(controller)
        reload_object(resource)
        reload_object(other)
        assert resource.get_latest_complete_set() is None
        assert other.get_latest_complete_set() is not None


class TestImportResources:
    def test_schedules_start_on_reactor_and_returns_immediately(self, mocker):
        mock_reactor = mocker.patch("maasserver.bootresources.reactor")

        result = bootresources.import_resources()

        assert result is None
        mock_reactor.callFromThread.assert_called_once()
        [scheduled], _ = mock_reactor.callFromThread.call_args
        assert callable(scheduled)

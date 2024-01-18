import hashlib
from hashlib import sha256
import os
from pathlib import Path
import shutil

from django.db import connection
import pytest

from maasserver.bootresources import (
    export_images_from_db,
    initialize_image_storage,
)
from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, BOOT_RESOURCE_TYPE
from maasserver.fields import LargeObjectFile
from maasserver.models import (
    BootResourceFile,
    BootResourceSet,
    RegionController,
)
from maasserver.models.largefile import LargeFile
from maasserver.utils.orm import reload_object
from provisioningserver.config import ClusterConfiguration


@pytest.fixture
def controller(factory):
    controller = factory.make_RegionRackController()
    yield controller


@pytest.fixture
def maas_data_dir(mocker, tmpdir):
    mocker.patch.dict(os.environ, {"MAAS_DATA": str(tmpdir)})
    yield tmpdir


@pytest.fixture
def image_store_dir(mocker, maas_data_dir):
    store = Path(maas_data_dir) / "boot-resources"
    store.mkdir()
    yield store
    shutil.rmtree(store)


@pytest.fixture
def tftp_root(mocker, image_store_dir, tmpdir):
    tftp_root = Path(image_store_dir) / "tftp_root"
    tftp_root.mkdir(parents=True)
    config = Path(tmpdir) / Path(ClusterConfiguration.DEFAULT_FILENAME).name
    with ClusterConfiguration.open_for_update(config) as cfg:
        cfg.tftp_root = str(tftp_root)
    mocker.patch.dict(os.environ, {"MAAS_CLUSTER_CONFIG": str(config)})
    yield tftp_root


def list_files(base_path):
    return {str(path.relative_to(base_path)) for path in base_path.iterdir()}


def make_LargeFile(factory, content: bytes = None, size=None):
    if content is None:
        content_size = size
        if content_size is None:
            content_size = 512
        content = factory.make_bytes(size=content_size)
    if size is None:
        size = len(content)
    sha256 = hashlib.sha256()
    sha256.update(content)
    digest = sha256.hexdigest()
    largeobject = LargeObjectFile()
    with largeobject.open("wb") as stream:
        stream.write(content)
    return LargeFile.objects.create(
        sha256=digest,
        size=len(content),
        total_size=size,
        content=largeobject,
    )


def make_boot_resource_file_with_content_largefile(
    factory,
    resource_set: BootResourceSet,
    filename: str | None = None,
    filetype: str | None = None,
    extra: str | None = None,
    content: bytes | None = None,
    size: int | None = None,
    regions: list[RegionController] | None = None,
) -> BootResourceFile:
    largefile = make_LargeFile(factory, content=content, size=size)
    return factory.make_BootResourceFile(
        resource_set,
        filename=filename,
        filetype=filetype,
        size=largefile.size,
        sha256=largefile.sha256,
        extra=extra,
        largefile=largefile,
        synced=[(r, -1) for r in regions] if regions else None,
    )


@pytest.mark.usefixtures("maasdb")
class TestExportImagesFromDB:
    def test_create_files(self, controller, image_store_dir, factory):
        resource1 = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set1 = factory.make_BootResourceSet(
            resource=resource1,
            version="20230901",
            label="stable",
        )
        content1 = b"ubuntu-jammy"
        make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set1,
            filename="boot-initrd",
            content=content1,
        )

        resource2 = factory.make_BootResource(
            name="centos/8",
            architecture="amd64/generic",
        )
        resource_set2 = factory.make_BootResourceSet(
            resource=resource2,
            version="20230830",
            label="candidate",
        )
        content2 = b"centos-8"
        make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set2,
            filename="boot-kernel",
            content=content2,
        )
        export_images_from_db(controller)
        assert list_files(image_store_dir) == {
            sha256(content1).hexdigest(),
            sha256(content2).hexdigest(),
        }

    def test_export_overwrite_changed(
        self, controller, image_store_dir, factory
    ):
        content = b"ubuntu-jammy"
        image = image_store_dir / sha256(content).hexdigest()
        image.write_bytes(b"old")

        resource = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set,
            filename="boot-initrd",
            content=content,
        )
        export_images_from_db(controller)
        assert image.read_bytes() == content

    def test_remove_largfile(self, controller, image_store_dir, factory):
        resource = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        resource_file = make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set,
            filename="boot-initrd",
            content=b"some content",
        )
        largefile = resource_file.largefile
        export_images_from_db(controller)

        assert reload_object(largefile) is None
        # largeobject also gets deleted
        with connection.cursor() as cursor:
            cursor.execute("SELECT loid FROM pg_largeobject")
            assert cursor.fetchall() == []

    def test_no_largefile_ignore(self, controller, image_store_dir, factory):
        resource = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        sha256 = "abcde"
        factory.make_BootResourceFile(
            resource_set=resource_set,
            largefile=None,
            filename="boot-initrd",
            sha256=sha256,
            size=100,
        )

        resource_file = image_store_dir / sha256
        resource_file.touch()
        export_images_from_db(controller)
        assert resource_file.exists()


@pytest.mark.usefixtures("maasdb")
class TestInitialiseImageStorage:
    def test_empty(self, controller, image_store_dir: Path):
        initialize_image_storage(controller)
        assert list_files(image_store_dir) == {"bootloaders"}

    def test_remove_extra_files(
        self, controller, image_store_dir: Path, tftp_root: Path
    ):
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

    def test_remove_extra_symlink(
        self, controller, image_store_dir: Path, tmp_path
    ):
        extra_dir = tmp_path / "somedir"
        extra_dir.mkdir(parents=True)
        extra_symlink = image_store_dir / "somelink"
        extra_symlink.symlink_to(extra_dir)

        initialize_image_storage(controller)
        assert not extra_symlink.exists()

    def test_missing_local_files(
        self, controller, image_store_dir: Path, factory
    ):
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

    def test_booloaders_export(
        self, controller, tmpdir, image_store_dir, factory
    ):
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name="grub-efi/uefi",
            architecture="amd64/generic",
            bootloader_type="uefi",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        tarball = Path(
            factory.make_tarball(
                tmpdir,
                {
                    "grubx64.efi": b"grub content",
                    "bootx64.efi": b"boot content",
                },
            )
        )
        make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set,
            filetype=BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ,
            filename="grub2-signed.tar.xz",
            content=tarball.read_bytes(),
            regions=[controller],
        )
        initialize_image_storage(controller)
        bootloader_dir = image_store_dir / "bootloaders/uefi/amd64"
        assert list_files(bootloader_dir) == {
            "grubx64.efi",
            "bootx64.efi",
        }

    def test_booloaders_export_already_exist(
        self, controller, tmpdir, image_store_dir, factory
    ):
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name="grub-efi/uefi",
            architecture="amd64/generic",
            bootloader_type="uefi",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        tarball = Path(
            factory.make_tarball(
                tmpdir,
                {
                    "grubx64.efi": b"grub content",
                    "bootx64.efi": b"boot content",
                },
            )
        )
        rfile = make_boot_resource_file_with_content_largefile(
            factory,
            resource_set=resource_set,
            filetype=BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ,
            filename="grub2-signed.tar.xz",
            content=tarball.read_bytes(),
            regions=[controller],
        )
        tarball.rename(rfile.local_file().path)
        initialize_image_storage(controller)
        bootloader_dir = image_store_dir / "bootloaders/uefi/amd64"
        assert list_files(bootloader_dir) == {
            "grubx64.efi",
            "bootx64.efi",
        }

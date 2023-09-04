from hashlib import sha256
from pathlib import Path

from django.db import connection
import pytest

from maasserver.bootresources import export_images_from_db
from maasserver.utils.orm import reload_object


@pytest.fixture
def target_dir(tmpdir):
    yield Path(tmpdir / "images-export")


def list_files(base_path):
    return {path.relative_to(base_path) for path in base_path.iterdir()}


@pytest.mark.usefixtures("maasdb")
class TestExportImagesFromDB:
    def test_empty(self, target_dir):
        export_images_from_db(target_dir)
        assert list(target_dir.iterdir()) == []

    def test_create_files(self, target_dir, factory):
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
        factory.make_boot_resource_file_with_content(
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
        factory.make_boot_resource_file_with_content(
            resource_set=resource_set2,
            filename="boot-kernel",
            content=content2,
        )
        export_images_from_db(target_dir)
        assert list_files(target_dir) == {
            Path(sha256(content1).hexdigest()),
            Path(sha256(content2).hexdigest()),
        }

    def test_remove_extra_files(self, target_dir, factory):
        target_dir.mkdir()
        extra_file = target_dir / "abcde"
        extra_file.write_text("some content")

        export_images_from_db(target_dir)
        assert not extra_file.exists()

    def test_export_overwrite_changed(self, target_dir, factory):
        target_dir.mkdir()

        content = b"ubuntu-jammy"
        image = target_dir / sha256(content).hexdigest()
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
        factory.make_boot_resource_file_with_content(
            resource_set=resource_set,
            filename="boot-initrd",
            content=content,
        )
        export_images_from_db(target_dir)
        assert image.read_bytes() == content

    def test_remove_largfile(self, target_dir, factory):
        resource = factory.make_BootResource(
            name="ubuntu/jammy",
            architecture="s390x/generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource=resource,
            version="20230901",
            label="stable",
        )
        resource_file = factory.make_boot_resource_file_with_content(
            resource_set=resource_set,
            filename="boot-initrd",
            content=b"some content",
        )
        largefile = resource_file.largefile
        export_images_from_db(target_dir)

        assert reload_object(largefile) is None
        # largeobject also gets deleted
        with connection.cursor() as cursor:
            cursor.execute("SELECT loid FROM pg_largeobject")
            assert cursor.fetchall() == []

import pytest

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE
from maasserver.forms import get_uploaded_filename


@pytest.mark.parametrize(
    "filetype, filename",
    [
        (BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ, "root.tgz"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_TBZ, "root.tbz"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_TXZ, "root.txz"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDTGZ, "root-dd"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDTAR, "root-dd.tar"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDRAW, "root-dd.raw"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDTBZ, "root-dd.tar.bz2"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDTXZ, "root-dd.tar.xz"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDBZ2, "root-dd.bz2"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDGZ, "root-dd.gz"),
        (BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ, "root-dd.xz"),
    ],
)
def test_get_uploaded_filename(filetype, filename):
    assert filename == get_uploaded_filename(filetype)

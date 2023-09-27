import pytest

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, BOOT_RESOURCE_TYPE
from maasserver.utils.osystems import OSReleaseArchitecture
from provisioningserver.enum import enum_choices

SUPPORTED_UPLOADED_TYPES = [
    BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
    BOOT_RESOURCE_FILE_TYPE.ROOT_TXZ,
]

UNSUPPORTED_UPLOADED_TYPES = [
    file_type
    for file_type, _ in enum_choices(BOOT_RESOURCE_FILE_TYPE)
    if file_type not in SUPPORTED_UPLOADED_TYPES
]

SUPPORTED_SYNCED_TYPES = [
    BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
]

UNSUPPORTED_SYNCED_TYPES = [
    file_type
    for file_type, _ in enum_choices(BOOT_RESOURCE_FILE_TYPE)
    if file_type not in SUPPORTED_SYNCED_TYPES
]


class TestOSReleaseArchitecture:
    @pytest.mark.parametrize(
        "file_type",
        [file_type for file_type in SUPPORTED_SYNCED_TYPES],
    )
    def test_can_deploy_to_memory_synced_supported(self, file_type: str):
        arch_release = OSReleaseArchitecture(
            name="my-release",
            image_type=BOOT_RESOURCE_TYPE.SYNCED,
            file_type=file_type,
        )
        assert arch_release.can_deploy_to_memory

    @pytest.mark.parametrize(
        "file_type",
        [file_type for file_type in UNSUPPORTED_SYNCED_TYPES],
    )
    def test_can_deploy_to_memory_synced_unsupported(self, file_type: str):
        arch_release = OSReleaseArchitecture(
            name="my-release",
            image_type=BOOT_RESOURCE_TYPE.SYNCED,
            file_type=file_type,
        )
        assert not arch_release.can_deploy_to_memory

    @pytest.mark.parametrize(
        "file_type",
        [file_type for file_type in SUPPORTED_UPLOADED_TYPES],
    )
    def test_can_deploy_to_memory_uploaded_supported(self, file_type: str):
        arch_release = OSReleaseArchitecture(
            name="my-release",
            image_type=BOOT_RESOURCE_TYPE.UPLOADED,
            file_type=file_type,
        )
        assert arch_release.can_deploy_to_memory

    @pytest.mark.parametrize(
        "file_type",
        [file_type for file_type in UNSUPPORTED_UPLOADED_TYPES],
    )
    def test_can_deploy_to_memory_uploaded_unsupported(self, file_type: str):
        arch_release = OSReleaseArchitecture(
            name="my-release",
            image_type=BOOT_RESOURCE_TYPE.UPLOADED,
            file_type=file_type,
        )
        assert not arch_release.can_deploy_to_memory

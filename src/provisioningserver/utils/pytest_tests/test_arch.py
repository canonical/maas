import random

import pytest

from provisioningserver.utils.arch import (
    debian_to_kernel_architecture,
    get_architecture,
    kernel_to_debian_architecture,
)


@pytest.fixture
def clear_arch_cache():
    get_architecture.cache_clear()
    yield
    get_architecture.cache_clear()


@pytest.mark.usefixtures("clear_arch_cache")
class TestGetArchitecture:
    def test_get_architecture_from_deb(self, mocker):
        arch = random.choice(["i386", "amd64", "arm64", "ppc64el"])
        mocker.patch(
            "apt_pkg.get_architectures", return_value=[arch, "otherarch"]
        )
        assert get_architecture() == arch

    def test_get_architecture_from_snap_env(
        self, mocker, monkeypatch, factory
    ):
        arch = factory.make_name("arch")
        mock_get_architectures = mocker.patch("apt_pkg.get_architectures")
        monkeypatch.setenv("SNAP_ARCH", arch)
        assert get_architecture() == arch
        mock_get_architectures.assert_not_called()


@pytest.mark.parametrize(
    "kernel_arch,debian_arch",
    [
        ("i686", "i386/generic"),
        ("x86_64", "amd64/generic"),
        ("aarch64", "arm64/generic"),
        ("ppc64le", "ppc64el/generic"),
        ("s390x", "s390x/generic"),
        ("mips", "mips/generic"),
        ("mips64", "mips64el/generic"),
    ],
)
class TestKernelAndDebianArchitectures:
    def test_kernel_to_debian_architecture(self, kernel_arch, debian_arch):
        assert kernel_to_debian_architecture(kernel_arch) == debian_arch

    def test_debian_to_kernel_architecture(self, kernel_arch, debian_arch):
        assert debian_to_kernel_architecture(debian_arch) == kernel_arch

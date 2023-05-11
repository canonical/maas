import lxml.etree
import pytest

from provisioningserver.drivers.pod.virsh import (
    DOM_TEMPLATE_AMD64,
    DOM_TEMPLATE_ARM64,
    DOM_TEMPLATE_PPC64,
    DOM_TEMPLATE_S390X,
)


@pytest.mark.parametrize(
    "arch,template",
    [
        ("amd64", DOM_TEMPLATE_AMD64),
        ("arm64", DOM_TEMPLATE_ARM64),
        ("ppc64", DOM_TEMPLATE_PPC64),
        ("s390x", DOM_TEMPLATE_S390X),
    ],
)
def test_template_has_passthrough(arch, template):
    element = lxml.etree.fromstring(template)
    cpus = element.iter("cpu")
    assert [cpu.get("mode") for cpu in cpus] == [
        "host-passthrough"
    ], f"Failed to find passthrough for {arch}"

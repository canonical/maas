from django.core.exceptions import ValidationError
import pytest

from maasserver.models.script import (
    translate_hardware_type,
    translate_script_parallel,
    translate_script_type,
)
from metadataserver.enum import HARDWARE_TYPE, SCRIPT_PARALLEL, SCRIPT_TYPE


def iter_test_values(*values):
    """Return an iterator with 2-tuples of test values for parametric tests."""
    for value in values:
        yield (value, value)
        yield (str(value), value)


@pytest.mark.parametrize(
    "value,script_type",
    [
        *iter_test_values(
            SCRIPT_TYPE.TESTING, SCRIPT_TYPE.COMMISSIONING, SCRIPT_TYPE.RELEASE
        ),
        ("test", SCRIPT_TYPE.TESTING),
        ("testing", SCRIPT_TYPE.TESTING),
        ("commission", SCRIPT_TYPE.COMMISSIONING),
        ("commissioning", SCRIPT_TYPE.COMMISSIONING),
        ("release", SCRIPT_TYPE.RELEASE),
    ],
)
def test_translate_script_type_valid(value, script_type):
    assert translate_script_type(value) == script_type


@pytest.mark.parametrize(
    "value,exception_text",
    [
        (132, "Invalid script type numeric value."),
        (
            "invalid-type",
            "Script type must be commissioning, testing or release",
        ),
    ],
)
def test_translate_script_type_invalid(value, exception_text):
    with pytest.raises(ValidationError) as err:
        translate_script_type(value)
    assert exception_text in str(err.value)


@pytest.mark.parametrize(
    "value,hardware_type",
    [
        *iter_test_values(
            HARDWARE_TYPE.NODE,
            HARDWARE_TYPE.CPU,
            HARDWARE_TYPE.GPU,
            HARDWARE_TYPE.MEMORY,
            HARDWARE_TYPE.STORAGE,
            HARDWARE_TYPE.NETWORK,
        ),
        ("node", HARDWARE_TYPE.NODE),
        ("controller", HARDWARE_TYPE.NODE),
        ("other", HARDWARE_TYPE.NODE),
        ("generic", HARDWARE_TYPE.NODE),
        ("cpu", HARDWARE_TYPE.CPU),
        ("processor", HARDWARE_TYPE.CPU),
        ("memory", HARDWARE_TYPE.MEMORY),
        ("ram", HARDWARE_TYPE.MEMORY),
        ("storage", HARDWARE_TYPE.STORAGE),
        ("disk", HARDWARE_TYPE.STORAGE),
        ("ssd", HARDWARE_TYPE.STORAGE),
        ("network", HARDWARE_TYPE.NETWORK),
        ("net", HARDWARE_TYPE.NETWORK),
        ("interface", HARDWARE_TYPE.NETWORK),
        ("gpu", HARDWARE_TYPE.GPU),
        ("graphics", HARDWARE_TYPE.GPU),
    ],
)
def test_translate_hardware_type_valid(value, hardware_type):
    translate_hardware_type(value) == hardware_type  # noqa: B015


@pytest.mark.parametrize(
    "value,exception_text",
    [
        (132, "Invalid hardware type numeric value."),
        (
            "invalid-type",
            "Hardware type must be node, cpu, memory, storage, or gpu",
        ),
    ],
)
def test_translate_hardware_type_invalid(value, exception_text):
    with pytest.raises(ValidationError) as err:
        translate_hardware_type(value)
    assert exception_text in str(err.value)


@pytest.mark.parametrize(
    "value,script_type",
    [
        *iter_test_values(
            SCRIPT_PARALLEL.DISABLED,
            SCRIPT_PARALLEL.INSTANCE,
            SCRIPT_PARALLEL.ANY,
        ),
        ("disabled", SCRIPT_PARALLEL.DISABLED),
        ("none", SCRIPT_PARALLEL.DISABLED),
        ("instance", SCRIPT_PARALLEL.INSTANCE),
        ("name", SCRIPT_PARALLEL.INSTANCE),
        ("any", SCRIPT_PARALLEL.ANY),
        ("enabled", SCRIPT_PARALLEL.ANY),
    ],
)
def test_translate_script_parallel_valid(value, script_type):
    assert translate_script_parallel(value) == script_type


@pytest.mark.parametrize(
    "value,exception_text",
    [
        (132, "Invalid script parallel numeric value."),
        (
            "invalid-type",
            "Script parallel must be disabled, instance, or any.",
        ),
    ],
)
def test_translate_script_parallel_invalid(value, exception_text):
    with pytest.raises(ValidationError) as err:
        translate_script_parallel(value)
    assert exception_text in str(err.value)

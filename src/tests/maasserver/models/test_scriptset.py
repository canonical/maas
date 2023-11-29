from django.core.exceptions import ValidationError
import pytest

from maasserver.models.scriptset import translate_result_type
from metadataserver.enum import RESULT_TYPE, RESULT_TYPE_CHOICES


class TestLoadBuiltinScripts:
    @pytest.mark.parametrize(
        "value, translated",
        [
            ("test", RESULT_TYPE.TESTING),
            ("testing", RESULT_TYPE.TESTING),
            ("commission", RESULT_TYPE.COMMISSIONING),
            ("commissioning", RESULT_TYPE.COMMISSIONING),
            ("install", RESULT_TYPE.INSTALLATION),
            ("installation", RESULT_TYPE.INSTALLATION),
            ("release", RESULT_TYPE.RELEASE),
            # numeric values
            *((value, value) for value, _ in RESULT_TYPE_CHOICES),
            # numeric values as strings
            *((str(value), value) for value, _ in RESULT_TYPE_CHOICES),
        ],
    )
    def test_valid_value(self, value, translated):
        assert translate_result_type(value) == translated

    @pytest.mark.parametrize(
        "value,error_message",
        [
            (100, "Invalid result type numeric value"),
            ("unknown", "Invalid result type name"),
        ],
    )
    def tet_invalid_value(self, value, error_message):
        with pytest.raises(ValidationError) as error:
            translate_result_type(value)
        assert error_message in str(error.value)

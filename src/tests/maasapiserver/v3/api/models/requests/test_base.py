import pytest

from maasapiserver.v3.api.models.requests.base import NamedBaseModel


class TestNamedBaseModel:
    @pytest.mark.parametrize(
        "name",
        [
            "ValidName",
            "Name With Spaces",
            "Name-With-Hyphens",
            "123ValidName",
            "name with trailing hyphens-",
        ],
    )
    def test_valid_names(self, name: str):
        assert NamedBaseModel(name=name).name == name

    @pytest.mark.parametrize(
        "name",
        [
            "Name_With_Special#Characters",
            "",
            " ",
            "-Name with leading hyphens",
        ],
    )
    def test_invalid_names(self, name: str):
        with pytest.raises(ValueError, match="Invalid entity name."):
            NamedBaseModel(name=name)

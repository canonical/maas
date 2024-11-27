import pytest

from maasapiserver.v3.api.public.models.requests.base import (
    NamedBaseModel,
    OptionalNamedBaseModel,
)

VALID_NAMES = [
    "ValidName",
    "Name With Spaces",
    "Name-With-Hyphens",
    "123ValidName",
    "name with trailing hyphens-",
]

INVALID_NAMES = [
    "Name_With_Special#Characters",
    "",
    " ",
    "-Name with leading hyphens",
]


class TestNamedBaseModel:
    @pytest.mark.parametrize(
        "name",
        VALID_NAMES,
    )
    def test_valid_names(self, name: str):
        assert NamedBaseModel(name=name).name == name

    @pytest.mark.parametrize(
        "name",
        INVALID_NAMES,
    )
    def test_invalid_names(self, name: str):
        with pytest.raises(ValueError, match="Invalid entity name."):
            NamedBaseModel(name=name)


class TestOptionalNamedBaseModel:
    @pytest.mark.parametrize("name", VALID_NAMES)
    def test_valid_names(self, name: str):
        assert OptionalNamedBaseModel(name=name).name == name

    @pytest.mark.parametrize("name", INVALID_NAMES)
    def test_invalid_names(self, name: str):
        with pytest.raises(ValueError, match="Invalid entity name."):
            OptionalNamedBaseModel(name=name)

    def test_none_name(self):
        model = OptionalNamedBaseModel()
        assert model.name is None

# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel, ValidationError
import pytest

from maasservicelayer.models.fields import MacAddress


class TestMacAddress:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("", ""),
            ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
            ("AA-BB-CC-DD-EE-FF", "aa:bb:cc:dd:ee:ff"),
            ("aabb.ccdd.eeff", "aa:bb:cc:dd:ee:ff"),
            ("0:11:22:33:44:55", "00:11:22:33:44:55"),
        ],
    )
    def test_validate(self, value, expected):
        assert str(MacAddress(value)) == expected

    @pytest.mark.parametrize("value", ["nope", "aa:bb:cc:dd:ee", "zz:..."])
    def test_validate_rejects_invalid(self, value):
        with pytest.raises(ValueError):
            MacAddress(value)

    def test_in_pydantic_model_allows_empty_and_none(self):
        class Model(BaseModel):
            mac: MacAddress | None = None

        assert Model(mac="").mac == ""
        assert Model(mac=None).mac is None
        assert Model(mac="AA-BB-CC-DD-EE-FF").mac == "aa:bb:cc:dd:ee:ff"

    def test_in_pydantic_model_rejects_invalid(self):
        class Model(BaseModel):
            mac: MacAddress | None = None

        with pytest.raises(ValidationError):
            Model(mac="nope")

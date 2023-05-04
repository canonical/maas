from django.core.exceptions import ValidationError
import pytest

from maasserver.fields import MACAddressFormField, normalise_macaddress


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("aabbccddeeff", "aa:bb:cc:dd:ee:ff"),
        ("aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
        ("aa:b:cc:d:ee:f", "aa:0b:cc:0d:ee:0f"),
        ("aa-bb-cc-dd-ee-ff", "aa:bb:cc:dd:ee:ff"),
        ("aa-b-cc-d-ee-f", "aa:0b:cc:0d:ee:0f"),
        ("aabb.ccdd.eeff", "aa:bb:cc:dd:ee:ff"),
        ("abb.cdd.eeff", "0a:bb:0c:dd:ee:ff"),
    ],
)
def test_normalise_mac_address(value, expected):
    assert normalise_macaddress(value) == expected


class TestMACAddressFormField:
    def test_validate_valid(self):
        assert MACAddressFormField().validate("aa-bb-cc-dd-ee-ff") is None

    def test_validate_invalid(self):
        with pytest.raises(ValidationError):
            MACAddressFormField().validate("invalid")

    @pytest.mark.parametrize("value", ["", None])
    def test_validate_empty(self, value):
        assert MACAddressFormField().validate(value) is None

    def test_normalise_mac_format(self):
        assert (
            MACAddressFormField().clean("aa-bb-cc-dd-ee-ff")
            == "aa:bb:cc:dd:ee:ff"
        )

from maastesting.testcase import MAASTestCase
from provisioningserver.enum import enum_choices


class SampleEnum:
    ONE = "one"
    TWO = "two"


class TestEnumChoices(MAASTestCase):
    def test_values(self):
        self.assertEqual(
            enum_choices(SampleEnum),
            (("one", "one"), ("two", "two")),
        )

    def test_values_transform(self):
        self.assertEqual(
            enum_choices(SampleEnum, transform=str.upper),
            (("one", "ONE"), ("two", "TWO")),
        )

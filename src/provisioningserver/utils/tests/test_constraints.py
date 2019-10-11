# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for constraints helpers."""

__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.utils.constraints import (
    LabeledConstraintMap,
    parse_labeled_constraint_map,
    validate_constraint_label_name,
)
from testtools import ExpectedException
from testtools.matchers import Equals, HasLength, Is


class ConstraintTestException(Exception):
    """Dummy exception class used to test that specifying an exception class
    to throw works properly."""


class TestValidateLabelName(MAASTestCase):
    EXPECTED_BAD_NAMES = ["", " ", "_", "-", " ", "a ", "a ", "-a", "*", "%"]

    EXPECTED_GOOD_NAMES = ["a", "0", "A", "a-", "a-b", "a_b", "a_b"]

    def test__rejects_bad_names(self):
        for name in self.EXPECTED_BAD_NAMES:
            with ExpectedException(
                ConstraintTestException, msg="name=%s" % name
            ):
                validate_constraint_label_name(
                    name, exception_type=ConstraintTestException
                )

    def test__accepts_good_names(self):
        for name in self.EXPECTED_GOOD_NAMES:
            validate_constraint_label_name(name)


class TestGetLabeledConstraintsMap(MAASTestCase):
    def test__missing_key_value_pair_raises(self):
        with ExpectedException(ConstraintTestException):
            parse_labeled_constraint_map(
                "a:bc", exception_type=ConstraintTestException
            )

    def test__duplicate_label_raises(self):
        with ExpectedException(ConstraintTestException):
            parse_labeled_constraint_map(
                "a:b=c;a:d=e", exception_type=ConstraintTestException
            )

    def test__invalid_label_raises(self):
        with ExpectedException(ConstraintTestException):
            parse_labeled_constraint_map(
                "*:b=c", exception_type=ConstraintTestException
            )

    def test__label_with_no_constraints_raises(self):
        with ExpectedException(ConstraintTestException):
            parse_labeled_constraint_map(
                "a:", exception_type=ConstraintTestException
            )

    def test__single_value_map(self):
        result = parse_labeled_constraint_map("a:b=c")
        self.assertThat(result, Equals({"a": {"b": ["c"]}}))

    def test__non_string_returns_None(self):
        result = parse_labeled_constraint_map(dict())
        self.assertThat(result, Is(None))

    def test__empty_string_returns_empty_map(self):
        result = parse_labeled_constraint_map("")
        self.assertThat(result, Equals({}))

    def test__multiple_value_map(self):
        result = parse_labeled_constraint_map("a:b=c,d=e")
        self.assertThat(result, Equals({"a": {"b": ["c"], "d": ["e"]}}))

    def test__multiple_value_map_with_duplicate_keys_appends_to_list(self):
        result = parse_labeled_constraint_map("a:a=abc,a=def,a=ghi")
        self.assertThat(result, Equals({"a": {"a": ["abc", "def", "ghi"]}}))

    def test__multiple_label_map(self):
        result = parse_labeled_constraint_map("foo:a=b;bar:c=d")
        self.assertThat(
            result, Equals({"foo": {"a": ["b"]}, "bar": {"c": ["d"]}})
        )

    def test__multiple_value_map_multiple_label_map(self):
        result = parse_labeled_constraint_map("foo:a=b,c=d;bar:e=f,g=h")
        self.assertThat(
            result,
            Equals(
                {
                    "foo": {"a": ["b"], "c": ["d"]},
                    "bar": {"e": ["f"], "g": ["h"]},
                }
            ),
        )


class TestLabeledConstraintMap(MAASTestCase):
    def test__len__for_null_map(self):
        lcm = LabeledConstraintMap(None)
        self.assertThat(lcm, HasLength(0))

    def test__len__for_empty_map(self):
        lcm = LabeledConstraintMap("")
        self.assertThat(lcm, HasLength(0))

    def test__len__for_populated_map(self):
        lcm = LabeledConstraintMap("eth0:space=1;eth1:space=2")
        self.assertThat(lcm, HasLength(2))

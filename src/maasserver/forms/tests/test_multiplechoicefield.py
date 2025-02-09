# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for multiple-choice fields."""

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from maasserver.forms import (
    UnconstrainedMultipleChoiceField,
    ValidatorMultipleChoiceField,
)
from maasserver.testing.testcase import MAASServerTestCase


class TestUnconstrainedMultipleChoiceField(MAASServerTestCase):
    def test_accepts_list(self):
        value = ["a", "b"]
        instance = UnconstrainedMultipleChoiceField()
        self.assertEqual(value, instance.clean(value))


class TestValidatorMultipleChoiceField(MAASServerTestCase):
    def test_field_validates_valid_data(self):
        value = ["test@example.com", "me@example.com"]
        field = ValidatorMultipleChoiceField(validator=validate_email)
        self.assertEqual(value, field.clean(value))

    def test_field_uses_validator(self):
        value = ["test@example.com", "invalid-email"]
        field = ValidatorMultipleChoiceField(validator=validate_email)
        error = self.assertRaises(ValidationError, field.clean, value)
        self.assertEqual(["Enter a valid email address."], error.messages)

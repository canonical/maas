# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import re

import pytest

from maascommon.utils.password import generate_password


class TestGeneratePassword:
    def test_generates_minimum_14_characters(self):
        password = generate_password()
        assert len(password) >= 14

    def test_generates_requested_length(self):
        for length in [14, 16, 20, 32]:
            password = generate_password(length=length)
            assert len(password) == length

    def test_raises_error_if_length_less_than_14(self):
        with pytest.raises(ValueError, match="at least 14 characters"):
            generate_password(length=10)

    def test_falls_back_to_rule_based_generation_if_max_attempts_exhausted(
        self,
    ):
        password = generate_password(length=14, max_attempts=0)
        assert len(password) == 14
        assert re.search(r"[A-Z]", password)
        assert re.search(r"\d", password)
        assert re.search(r"[^a-zA-Z0-9]", password)

    def test_contains_uppercase_letter(self):
        for _ in range(10):
            password = generate_password()
            assert re.search(r"[A-Z]", password), (
                f"Password missing uppercase: {password}"
            )

    def test_contains_digit(self):
        for _ in range(10):
            password = generate_password()
            assert re.search(r"\d", password), (
                f"Password missing digit: {password}"
            )

    def test_contains_special_character(self):
        for _ in range(10):
            password = generate_password()
            assert re.search(r"[^a-zA-Z0-9]", password), (
                f"Password missing special char: {password}"
            )

    def test_contains_lowercase_letter(self):
        for _ in range(10):
            password = generate_password()
            assert re.search(r"[a-z]", password), (
                f"Password missing lowercase: {password}"
            )

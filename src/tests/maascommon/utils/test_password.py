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
            password = generate_password(min_length=length, max_length=length)
            assert len(password) == length

    def test_generates_length_within_range(self):
        for _ in range(20):
            password = generate_password(min_length=14, max_length=20)
            assert 14 <= len(password) <= 20

    def test_raises_error_if_min_length_less_than_14(self):
        with pytest.raises(ValueError, match="at least 14 characters"):
            generate_password(min_length=10, max_length=10)

    def test_raises_error_if_max_length_less_than_min_length(self):
        with pytest.raises(ValueError, match="max_length"):
            generate_password(min_length=20, max_length=14)

    def test_falls_back_to_rule_based_generation_if_max_attempts_exhausted(
        self,
    ):
        password = generate_password(
            min_length=14, max_length=14, max_attempts=0
        )
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

    def test_extra_constraint_is_enforced(self, monkeypatch):
        # First candidate satisfies neither the complexity policy nor the
        # extra_constraint; second satisfies both. Mocking the candidate
        # generator keeps this deterministic rather than relying on the
        # odds of a random candidate matching an arbitrary constraint.
        candidates = iter(["a" * 14, "Aaa1!" + "a" * 9])
        monkeypatch.setattr(
            "maascommon.utils.password._generate_base64_password",
            lambda length: next(candidates),
        )
        password = generate_password(
            extra_constraint=lambda pwd: pwd.startswith("A")
        )
        assert password.startswith("A")

    def test_extra_constraint_checked_on_rule_based_fallback(self):
        # The rule-based fallback guarantees a digit by construction, so an
        # extra_constraint relying on that is always satisfied, even though
        # the fallback is only tried once (not retried).
        password = generate_password(
            max_attempts=0,
            extra_constraint=lambda pwd: bool(re.search(r"\d", pwd)),
        )
        assert re.search(r"\d", password)

    def test_fallback_error_if_extra_constraint_not_satisfiable(self):
        with pytest.raises(ValueError, match="satisfying all constraints"):
            generate_password(
                max_attempts=0, extra_constraint=lambda pwd: False
            )

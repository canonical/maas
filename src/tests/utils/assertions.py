#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).


def assert_unordered_items_equal(actual: list, expected: list):
    """
    Asserts that two lists contain the same items in the same order.

    Parameters:
    actual (list): The actual list to be tested.
    expected (list): The expected list to compare against.

    Raises:
    AssertionError: If the lists differ in length or contain different elements.
    """
    assert len(actual) == len(expected), (
        f"List lengths differ: expected {len(expected)}, but got {len(actual)}.\n"
        f"Expected: {expected}\nActual: {actual}"
    )

    for i, (a, b) in enumerate(zip(sorted(actual), sorted(expected))):
        assert a == b, (
            f"Mismatch at index {i}: expected {b}, but got {a}.\n"
            f"Expected: {expected}\nActual: {actual}"
        )

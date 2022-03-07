import random
import string
from typing import Any, Mapping


def make_weighted_item_getter(item_weights: Mapping[Any, int]):
    """Choose a key from item_weights with probability given in values."""
    while True:
        yield random.choices(
            list(item_weights.keys()), list(item_weights.values())
        )[0]


def range_one(count: int) -> range:
    return range(1, count + 1)


def make_name(size=6, lowercase=True) -> str:
    letters = string.ascii_lowercase if lowercase else string.ascii_letters
    return "".join(random.choices(letters + string.digits, k=size))

import random
import string


class WeightedItemGetter:
    """Get items based on probilibility."""

    def __init__(self, item_weights):
        self.item_cum_weights = {}
        self.max_cum_weight = 0
        for item, weight in item_weights.items():
            self.item_cum_weights[item] = weight + self.max_cum_weight
            self.max_cum_weight += weight

    def __next__(self):
        value = random.randint(1, self.max_cum_weight)
        for item, cum_weight in self.item_cum_weights.items():
            if value <= cum_weight:
                return item


def range_one(count: int) -> range:
    return range(1, count + 1)


def make_name(size=6, lowercase=True) -> str:
    letters = string.ascii_lowercase if lowercase else string.ascii_letters
    return "".join(random.choices(letters + string.digits, k=size))

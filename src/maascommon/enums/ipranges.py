from enum import Enum


class IPRangeType(str, Enum):
    """The vocabulary of possible types of `IPRange` objects."""

    # Dynamic IP Range.
    DYNAMIC = "dynamic"

    # Reserved for exclusive use by MAAS (and possibly a particular user).
    RESERVED = "reserved"

    def __str__(self):
        return str(self.value)

from enum import StrEnum


class SshKeysProtocolType(StrEnum):
    # Launchpad
    LP = "lp"

    # Github
    GH = "gh"

    def __str__(self):
        return str(self.value)

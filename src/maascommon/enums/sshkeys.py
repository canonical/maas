from enum import StrEnum


class SshKeysProtocolType(StrEnum):
    # Launchpad
    LP = "lp"

    # Github
    GH = "gh"

    def __str__(self):
        return str(self.value)


OPENSSH_PROTOCOL2_KEY_TYPES = frozenset(
    (
        "ecdsa-sha2-nistp256",
        "ecdsa-sha2-nistp384",
        "ecdsa-sha2-nistp521",
        "sk-ecdsa-sha2-nistp256@openssh.com",
        "sk-ssh-ed25519@openssh.com",
        "ssh-ed25519",
        "ssh-rsa",
    )
)

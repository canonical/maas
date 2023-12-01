# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.utils.sshkey`."""


import re

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.sshkey import (
    normalise_openssh_public_key,
    OpenSSHKeyError,
)

example_openssh_public_keys = {
    "ecdsa256": (
        "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAA"
        "ABBBEqp6hJ9qj6dD1Y1AfsbauzjAaoIQhvTCdg+otLRklg5ZWr8KoS98K50s0eVwcOD7i"
        "LltCeS7W0y8c7wlsADVh0= ec2@bar"
    ),
    "ecdsa384": (
        "ecdsa-sha2-nistp384 AAAAE2VjZHNhLXNoYTItbmlzdHAzODQAAAAIbmlzdHAzODQAA"
        "ABhBFnB+h79/2MeUR4FoDuKJDyjLEswi8I50NuwIoRbHOwPkPDSDXk6EKfBY0GEwAGyr7"
        "h9OjVlmA1KKWUE01KJKf4/iJOh+9zsaL4iQzP9Q9phiUAmxkvegefGwqEXeAvk1Q== "
        "ec3@bar"
    ),
    "ecdsa521": (
        "ecdsa-sha2-nistp521 AAAAE2VjZHNhLXNoYTItbmlzdHA1MjEAAAAIbmlzdHA1MjEAA"
        "ACFBAFid8WJ6720Z8xJ/Fnsz9eZmUxdbcVNzBeML380gMeBMP9zPXWz629cahQT0HncnK"
        "sLsbRB7MMxdaBdsAQ8pteGXQEHVdnr6IkOrVbCHtVaVbjN4gpRICseMnDHrryrOjsvBIU"
        "7GGpmmHZka9alvSZlbB1lCx1BxqZZj8AHjJq2KpUh+A== ec5@bar"
    ),
    "dsa": (
        "ssh-dss AAAAB3NzaC1kc3MAAACBALl8PCMaSa3pCCGJaJr4kH0QPlrgyG3Lka+/y4xx1"
        "dOuJhpsLe2V9+CKX7Sz1yphCs26KqMFe/ebYGAUDhTdVlE4/TgpAP4GiTjdO1FGXTYdgQ"
        "yJpfp50bTUW0zKIP/dwHs5dCLn4XYAxXzSsvORGVQGbM6P6vh3lieTkeVETGZDAAAAFQC"
        "AaBKUmPvRqI37VRj1PE9B2rnkfQAAAIEApWYMF0IU+BYUtFuwRRUE9wEGxDEjTtuoWYCW"
        "ML7Zn+cFOvK+C0x8YItQ3xIiI3a/0DCoDPIZPvImXDMrs0zUunegndS9g7J0gCHFY9dd+"
        "rgYShUHwCI+hy/D9Dp1ukNnGD0bb3x5vEoSK6whrJWBM6is7TW4R5fvz/xDhrtIcxgAAA"
        "CBAJbZsmuuWN2kb7lD27IzKcOgd07esoHPWZnv4qg7xhS1GdVr485v73OW1rfpWU6Pdoh"
        "ckXLg9ZaoWtVTwNKTfHxS3iug9/pseBWTHdpmxCM5ClsZJii6T4frR5NTOCGKLxOamTs/"
        "//OXopZr5u3vT20NFlzFE95J86tGtxYPPivx ubuntu@server-7476"
    ),
    "ed25519": (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBEqkw2AgmkjqNjCFuiKXeUgLNmRbgVr8"
        "W2TlAvFybJv ed255@bar"
    ),
    "rsa": (
        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDdrzzDZNwyMVBvBTT6kBnrfPZv/AUbk"
        "xj7G5CaMTdw6xkKthV22EntD3lxaQxRKzQTfCc2d/CC1K4ushCcRs1S6SQ2zJ2jDq1UmO"
        "UkDMgvNh4JVhJYSKc6mu8i3s7oGSmBado5wvtlpSzMrscOpf8Qe/wmT5fH12KB9ipJqoF"
        "NQMVbVcVarE/v6wpn3GZC62YRb5iaz9/M+t92Qhu50W2u+KfouqtKB2lwIDDKZMww38Ex"
        "tdMouh2FZpxaoh4Uey5bRp3tM3JgnWcX6fyUOp2gxJRPIlD9rrZhX5IkEkZM8MQbdPTQL"
        "gIf98oFph5RG6w1t02BvI9nJKM7KkKEfBHt ubuntu@test_rsa0"
    ),
}


def remove_comment(key):
    """Remove the comment field from an OpenSSH public key.

    Preserves leading and intermediate whitespace where reasonable.
    """
    match = re.match(r"\s*\S+\s+\S+", key)
    assert match is not None, f"Could not find keytype and key in {key!r}"
    return match.group(0)


class TestNormaliseOpenSSHPublicKeyBasics(MAASTestCase):
    """Tests for `normalise_openssh_public_key`."""

    def test_rejects_keys_with_fewer_than_2_parts(self):
        example_key = factory.make_name("key")
        error = self.assertRaises(
            OpenSSHKeyError, normalise_openssh_public_key, example_key
        )
        self.assertEqual(
            str(error),
            "Key should contain 2 or more space separated parts (key type, "
            "base64-encoded key, optional comments), not 1: " + example_key,
        )


class _TestNormaliseOpenSSHPublicKeyCommon:
    """Mix-in tests for `normalise_openssh_public_key`.

    Providing tests that are common to keys with and without comments.
    """

    def test_roundtrip(self):
        self.assertEqual(self.key, normalise_openssh_public_key(self.key))

    def test_rejects_keys_of_unrecognised_type(self):
        _, rest = self.key.split(None, 1)
        example_type = factory.make_name("type")
        example_key = example_type + " " + rest
        error = self.assertRaises(
            OpenSSHKeyError, normalise_openssh_public_key, example_key
        )
        self.assertTrue(
            str(error).startswith(
                f"Key type {example_type} not recognised; it should be one of: "
            )
        )

    def test_rejects_corrupt_keys(self):
        parts = self.key.split()
        parts[1] = parts[1][:-1]  # Remove one character from the key.
        example_key = " ".join(parts)
        error = self.assertRaises(
            OpenSSHKeyError, normalise_openssh_public_key, example_key
        )
        self.assertEqual(
            "Key could not be converted to RFC4716 form.", str(error)
        )


class TestNormaliseOpenSSHPublicKeyWithComments(
    _TestNormaliseOpenSSHPublicKeyCommon, MAASTestCase
):
    """Tests for `normalise_openssh_public_key` for keys with comments."""

    scenarios = sorted(
        (name, dict(key=key))
        for name, key in example_openssh_public_keys.items()
    )

    def test_normalises_mixed_whitespace(self):
        parts = self.key.split()
        example_key = "  %s \t %s\n  %s\r\n" % tuple(parts)
        self.assertEqual(self.key, normalise_openssh_public_key(example_key))

    def test_normalises_mixed_whitespace_in_comments(self):
        extra_comments = factory.make_name("foo"), factory.make_name("bar")
        example_key = self.key + " \t " + " \n\r ".join(extra_comments) + "\n"
        expected_key = self.key + " " + " ".join(extra_comments)
        self.assertEqual(
            expected_key, normalise_openssh_public_key(example_key)
        )


class TestNormaliseOpenSSHPublicKeyWithoutComments(
    _TestNormaliseOpenSSHPublicKeyCommon, MAASTestCase
):
    """Tests for `normalise_openssh_public_key` for keys without comments."""

    scenarios = sorted(
        (name, dict(key=remove_comment(key)))
        for name, key in example_openssh_public_keys.items()
    )

    def test_normalises_mixed_whitespace(self):
        parts = self.key.split()
        example_key = "  %s \t %s\r\n" % tuple(parts)
        self.assertEqual(self.key, normalise_openssh_public_key(example_key))

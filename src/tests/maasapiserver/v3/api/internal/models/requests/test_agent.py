#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasapiserver.v3.api.internal.models.requests.agent import (
    AgentEnrollRequest,
)
from maasservicelayer.exceptions.catalog import ValidationException

"""
Instructions to generate a Certificate Signing Request (CSR) with certain
Common Name (CN)

# generate a private key
$ openssl genrsa -out private.key 1024

# generate a CSR using that private key
$ openssl req -new -key private.key -out request.csr -subj "/CN=01f09d32-f508-6064-bd1c-c025a58dd068"

# now we have private.key and request.csr
# - inspect the raw CSR
$ cat request.csr
# - inspect the decode CSR and verify CN
$ openssl req -in request.csr -noout -text
"""
CSR = "\n".join(
    [
        "-----BEGIN CERTIFICATE REQUEST-----",
        "MIIBbjCB2AIBADAvMS0wKwYDVQQDDCQwMWYwOWQzMi1mNTA4LTYwNjQtYmQxYy1j",
        "MDI1YTU4ZGQwNjgwgZ8wDQYJKoZIhvcNAQEBBQADgY0AMIGJAoGBAKuwhG8GrttS",
        "Jn8IFtagVM9b0e6OIor+mt00hSz9sf/U+q03QpDXVhkumU4EoJlU8EFqCANMClwX",
        "pmEI4xmRjr8DUgIP7zuTu8wacaQCoHMWvxg8sTb66G3FaD0tDqo4S6/31Ea4LDZ4",
        "ycdn2/cT9BLCdNazt/NxAdWAeYtB4ASHAgMBAAGgADANBgkqhkiG9w0BAQsFAAOB",
        "gQB06a8a64WR3qZL1j1Q1jWVK1/d189s0jY0zW6DUlNdaPBSMD67asbqDB6uCacD",
        "on1EEkebWMQG3uLsXE37/t9a7rRvRIAqD+L45ukfbzgjZ1LQmDYSWLhWuTzgfm69",
        "KvJsHcrkPdJ2ETV9zhvIqBWasyhRYzjn0bOQ/jIuiMItyw==",
        "-----END CERTIFICATE REQUEST-----",
    ]
)


class TestAgentRequest:
    def test_validate_valid_csr(self) -> None:
        agent_request = AgentEnrollRequest(
            secret="secret",
            csr=CSR,
        )
        assert agent_request.secret == "secret"
        assert agent_request.csr == CSR

    def test_validate_invalid_csr(self) -> None:
        with pytest.raises(ValidationException) as e:
            AgentEnrollRequest(
                secret="secret",
                csr="invalid-csr",
            )
        assert "Invalid PEM certificate." == e.value.details[0].message

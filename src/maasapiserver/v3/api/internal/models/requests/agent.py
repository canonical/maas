#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from OpenSSL import crypto
from pydantic import BaseModel, Field, validator

from maasservicelayer.exceptions.catalog import ValidationException


class AgentEnrollRequest(BaseModel):
    secret: str = Field(
        description="Provide this secret as a proof of identity of the Agent"
    )
    csr: str = Field(
        description="The Certificate Signing Request (CSR) for the Agent's TLS "
        "certificate."
    )

    @validator("csr")
    def validate_csr(cls, value: str) -> str:
        try:
            crypto.load_certificate_request(
                crypto.FILETYPE_PEM, value.encode()
            )
        except Exception as e:
            raise ValidationException.build_for_field(
                field="csr",
                message="Invalid PEM certificate.",
            ) from e

        return value

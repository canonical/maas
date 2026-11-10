#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from fastapi import Query
from pydantic import BaseModel, Field, field_validator

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.api_tokens import ApiTokenClauseFactory
from maasservicelayer.utils.date import utcnow


class ApiTokenCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    expires_at: datetime = Field(
        description="Expiration date. Must be timezone-aware and in the future."
    )

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone.")
        if value <= utcnow():
            raise ValueError("expires_at must be in the future.")
        return value


class ApiTokenFiltersParams(BaseModel):
    include_revoked: bool = Field(
        Query(default=False, description="Include revoked tokens.")
    )

    def to_clauses(self) -> list[Clause]:
        return (
            []
            if self.include_revoked
            else [ApiTokenClauseFactory.not_revoked()]
        )

    def to_href_format(self) -> str:
        return "include_revoked=true" if self.include_revoked else ""


class AdminApiTokenFiltersParams(ApiTokenFiltersParams):
    user_id: int | None = Field(
        Query(default=None, description="Filter by owner user ID.")
    )

    def to_clauses(self) -> list[Clause]:
        clauses = super().to_clauses()
        if self.user_id is not None:
            clauses.append(ApiTokenClauseFactory.with_user_id(self.user_id))
        return clauses

    def to_href_format(self) -> str:
        parts = [super().to_href_format()]
        if self.user_id is not None:
            parts.append(f"user_id={self.user_id}")
        return "&".join(part for part in parts if part)


def combine_clauses(clauses: list[Clause]) -> Clause | None:
    return ClauseFactory.and_clauses(clauses) if clauses else None

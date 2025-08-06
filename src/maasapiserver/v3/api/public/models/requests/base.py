# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from copy import deepcopy
from re import compile
from typing import ClassVar, Optional

from fastapi import Query
from pydantic import BaseModel, Field, validator

from maasservicelayer.db.filters import OrderByClause, OrderByClauseFactory
from maasservicelayer.exceptions.catalog import ValidationException

# from src/maasserver/fields.py:31
MODEL_NAME_VALIDATOR = compile(r"^\w[ \w-]*$")


class NamedBaseModel(BaseModel):
    name: str = Field(description="The unique name of the entity.")

    # TODO: move to @field_validator when we migrate to pydantic 2.x
    @validator("name")
    def check_regex_name(cls, v: str) -> str:
        if not MODEL_NAME_VALIDATOR.match(v):
            raise ValueError("Invalid entity name.")
        return v


class OptionalNamedBaseModel(BaseModel):
    name: Optional[str] = Field(
        description="The unique name of the entity.", default=None
    )

    # TODO: move to @field_validator when we migrate to pydantic 2.x
    @validator("name")
    def check_regex_name(cls, v: str) -> str:
        # If the name is set, it must not be None and it must match the regex
        if v is not None and not MODEL_NAME_VALIDATOR.match(v):
            raise ValueError("Invalid entity name.")
        return v


class OrderByQueryFilter(BaseModel):
    order_by: Optional[list[str]] = Field(
        Query(
            default=None,
            title="Properties to order by. You can wrap the property with `asc()` or `desc()` to modify the ordering",
        )
    )
    _order_by_columns: ClassVar[dict[str, OrderByClause]] = Field(exclude=True)

    @classmethod
    def _clean_field(cls, field: str) -> str:
        """Return the field name, removing any 'desc(' or 'asc(' prefix and the suffix ')'."""
        return (
            field.removeprefix("asc(").removeprefix("desc(").removesuffix(")")
        )

    @validator("order_by")
    def check_order_by_fields(
        cls, v: Optional[list[str]]
    ) -> Optional[list[str]]:
        seen_fields = set()
        if not v:
            return None
        for elem in v:
            field = cls._clean_field(elem)
            if field not in cls._order_by_columns:
                raise ValidationException.build_for_field(
                    "order_by",
                    f"'{elem}' is not an allowed property.",
                    location="query",
                )
            if field in seen_fields:
                raise ValidationException.build_for_field(
                    "order_by",
                    f"'{field}' property was specified more than once.",
                    location="query",
                )
            seen_fields.add(field)

        return v

    def to_clauses(self) -> list[OrderByClause]:
        clauses = []
        if not self.order_by:
            return []
        for field in self.order_by:
            orig_clause = self._order_by_columns.get(self._clean_field(field))
            assert orig_clause is not None

            clause = deepcopy(orig_clause)

            if field.startswith("asc("):
                clause = OrderByClauseFactory.asc_clause(clause)
            else:
                clause = OrderByClauseFactory.desc_clause(clause)
            clauses.append(clause)

        return clauses

    def to_href_format(self) -> str:
        if not self.order_by:
            return ""
        s = "&".join([f"order_by={field}" for field in self.order_by])
        return s

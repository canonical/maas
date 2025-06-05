# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from lxml import etree
from pydantic import Field, validator

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.tags import TagBuilder
from maasservicelayer.exceptions.catalog import ValidationException


class TagRequest(NamedBaseModel):
    name: str = Field(
        description="The new tag name. Because the name will be used in urls, it should be short."
    )
    definition: str = Field(
        description=(
            "An XPATH query that is evaluated againstthe hardware_details"
            " stored for all nodes (i.e. the output of ``lshw -xml``)."
        ),
        default="",
    )
    comment: str = Field(
        description="A description of what fhe tag will be used for in natural language.",
        default="",
    )
    kernel_opts: str = Field(
        description=(
            "Nodes associated with this tag will add this string to their"
            " kernel options when booting. The value overrides the global"
            " ``kernel_opts`` setting. If more than one tag is associated with"
            " a node, command line will be concatenated from all associated"
            " tags, in alphabetic tag name order."
        ),
        default="",
    )

    @validator("definition")
    def validate_definition(cls, v: str):
        if v != "":
            try:
                etree.XPath(v)
            except etree.XPathSyntaxError as e:
                raise ValidationException.build_for_field(
                    field="definition",
                    message=f"Invalid xpath expression: {e}",
                ) from e
        return v

    def to_builder(self) -> TagBuilder:
        return TagBuilder(
            name=self.name,
            definition=self.definition,
            comment=self.comment,
            kernel_opts=self.kernel_opts,
        )

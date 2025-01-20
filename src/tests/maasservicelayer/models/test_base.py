#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from pydantic import ValidationError
import pytest

from maasservicelayer.models.base import (
    MaasBaseModel,
    make_builder,
    ResourceBuilder,
    Unset,
)


class DomainModel(MaasBaseModel):
    a: int
    b: str


class TestResourceBuilder:
    def test_builder_extends_resource_builder(self):
        DomainModelBuilder = make_builder(DomainModel)
        assert issubclass(DomainModelBuilder, ResourceBuilder)

    def test_builder_unset_fields(self):
        DomainModelBuilder = make_builder(DomainModel)
        builder = DomainModelBuilder()
        assert isinstance(builder.a, Unset)
        assert isinstance(builder.b, Unset)

    def test_builder_validates_input_types(self):
        DomainModelBuilder = make_builder(DomainModel)
        with pytest.raises(ValidationError):
            DomainModelBuilder(a="crash")

        with pytest.raises(ValidationError):
            DomainModelBuilder(b=[])

        with pytest.raises(ValidationError):
            DomainModelBuilder(a={})

    def test_builder_sets_values(self):
        DomainModelBuilder = make_builder(DomainModel)
        builder = DomainModelBuilder(a=1, b="test")
        assert builder.a == 1
        assert builder.b == "test"

# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from maascommon.openfga.base import OpenFGAEntitlementResourceType
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.resource_pools import (
    ResourcePoolClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.fields import UniqueList
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.openfga_tuples import (
    EntitlementsBuilderFactory,
    UndefinedEntitlementError,
)


class EntitlementRequest(BaseModel):
    resource_type: OpenFGAEntitlementResourceType = Field(
        description="The resource type (e.g. 'maas', 'pool')."
    )
    resource_id: int = Field(
        description="The resource ID. Must be 0 for 'maas' type."
    )
    entitlement: str = Field(description="The entitlement name.")

    async def to_builder(self, group_id: int, services: ServiceCollectionV3):
        try:
            factory = EntitlementsBuilderFactory.get_factory(
                self.entitlement, self.resource_type
            )
        except UndefinedEntitlementError as err:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE, message=str(err)
                    )
                ]
            ) from err

        if self.resource_type == OpenFGAEntitlementResourceType.POOL:
            pool_exists = await services.resource_pools.exists(
                QuerySpec(
                    where=ResourcePoolClauseFactory.with_ids(
                        [self.resource_id]
                    )
                )
            )
            if not pool_exists:
                raise NotFoundException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message=f"ResourcePool with id {self.resource_id} not found.",
                        )
                    ]
                )
        elif self.resource_type == OpenFGAEntitlementResourceType.MAAS:
            if self.resource_id != 0:
                raise BadRequestException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message="For 'maas' resource type, resource_id must be 0.",
                        )
                    ]
                )
        return factory.build_tuple(group_id, self.resource_id)


class BulkEntitlementDeleteItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_type: OpenFGAEntitlementResourceType = Field(
        description="The resource type (e.g. 'maas', 'pool')."
    )
    resource_id: int = Field(description="The resource ID.")
    entitlement: str = Field(description="The entitlement name.")


class BulkEntitlementDeleteRequest(BaseModel):
    items: Annotated[
        UniqueList[BulkEntitlementDeleteItem], Field(min_length=1)  # type: ignore[valid-type]
    ]

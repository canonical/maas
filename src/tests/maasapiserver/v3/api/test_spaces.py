# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.models.responses.spaces import SpacesListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.spaces import Space
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import (
    ApiCommonTests,
    EndpointDetails,
    PaginatedEndpointTestConfig,
)


class TestSpaceApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        def _assert_space_in_list(
            space: Space, spaces_response: SpacesListResponse
        ):
            space_response = next(
                filter(lambda resp: resp.id == space.id, spaces_response.items)
            )
            assert space.id == space_response.id
            assert space.name == space_response.name
            assert space.description == space_response.description

        async def create_pagination_test_resources(
            fixture: Fixture, size: int
        ) -> list[Space]:
            created_spaces = [
                await create_test_space_entry(
                    fixture, name=str(i), description=str(i)
                )
                for i in range(size)
            ]
            return created_spaces

        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/spaces",
                user_role=UserRole.USER,
                pagination_config=PaginatedEndpointTestConfig[
                    SpacesListResponse
                ](
                    response_type=SpacesListResponse,
                    create_resources_routine=create_pagination_test_resources,
                    assert_routine=_assert_space_in_list,
                ),
            )
        ]

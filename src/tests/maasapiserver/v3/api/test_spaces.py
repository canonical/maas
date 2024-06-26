# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from httpx import AsyncClient

from maasapiserver.v3.api.models.responses.spaces import SpacesListResponse
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.models.spaces import Space
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasapiserver.v3.api.base import ApiCommonTests, EndpointDetails


class TestSpaceApi(ApiCommonTests):
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        return [
            EndpointDetails(
                method="GET",
                path=f"{V3_API_PREFIX}/spaces",
                user_role=UserRole.USER,
            )
        ]

    def _assert_space_in_list(
        self, space: Space, spaces_response: SpacesListResponse
    ):
        space_response = next(
            filter(lambda resp: resp.id == space.id, spaces_response.items)
        )
        assert space.id == space_response.id
        assert space.name == space_response.name
        assert space.description == space_response.description

    # GET /spaces
    async def test_list(
        self, authenticated_user_api_client_v3: AsyncClient, fixture: Fixture
    ):
        created_spaces = [
            await create_test_space_entry(
                fixture, name=str(i), description=str(i)
            )
            for i in range(10)
        ]

        next_page_link = f"{V3_API_PREFIX}/spaces?size=2"
        last_page = 4
        for page in range(5):  # There should be 5 pages
            response = await authenticated_user_api_client_v3.get(
                next_page_link
            )
            space_response = SpacesListResponse(**response.json())
            assert space_response.kind == "SpacesList"
            assert len(space_response.items) == 2
            self._assert_space_in_list(created_spaces.pop(), space_response)
            self._assert_space_in_list(created_spaces.pop(), space_response)

            if page == last_page:
                assert space_response.next is None
            else:
                next_page_link = space_response.next

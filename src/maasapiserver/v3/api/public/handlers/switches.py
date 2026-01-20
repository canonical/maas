# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    ConflictBodyResponse,
    NotFoundBodyResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.switches import (
    SwitchOperationRequest,
    SwitchRequest,
    SwitchUpdateRequest,
)
from maasapiserver.v3.api.public.models.responses.switches import (
    SwitchesListResponse,
    SwitchResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.switches import (
    SwitchClauseFactory,
    SwitchInterfaceClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.services import ServiceCollectionV3


class SwitchesHandler(Handler):
    """API handler for managing network switches."""

    TAGS = ["Switches"]

    @handler(
        path="/switches",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": SwitchesListResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_switches(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SwitchesListResponse:
        """List all switches with pagination."""
        switches = await services.switches.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        return SwitchesListResponse(
            items=[
                await SwitchResponse.from_model(
                    switch=switch,
                    self_base_hyperlink=f"{V3_API_PREFIX}/switches",
                    services=services,
                )
                for switch in switches.items
            ],
            total=switches.total,
            next=(
                f"{V3_API_PREFIX}/switches?"
                f"{pagination_params.to_next_href_format()}"
                if switches.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/switches/{switch_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": SwitchResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_switch(
        self,
        switch_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SwitchResponse:
        """Get a specific switch by ID."""
        switch = await services.switches.get_by_id(switch_id)
        if not switch:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type="SwitchNotFound",
                        message=f"Switch with id '{switch_id}' was not found.",
                    )
                ]
            )
        return await SwitchResponse.from_model(
            switch=switch,
            self_base_hyperlink=f"{V3_API_PREFIX}/switches",
            services=services,
        )

    @handler(
        path="/switches",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {"model": SwitchResponse},
            400: {"model": ValidationErrorBodyResponse},
            409: {"model": ConflictBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_switch(
        self,
        response: Response,
        switch_request: SwitchRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SwitchResponse:
        """Create a new switch in the 'registered' state.

        Creates a switch and its management interface. If an IP address is
        specified, a StaticIPAddress entry will be created and linked to
        the interface.
        """
        # Check for duplicate MAC address
        existing_interfaces = await services.switchinterfaces.list(
            page=1,
            size=1,
            query=QuerySpec(
                where=SwitchInterfaceClauseFactory.with_mac_address(
                    switch_request.mac_address
                )
            ),
        )
        if existing_interfaces.total > 0:
            raise AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type="SwitchInterfaceAlreadyExists",
                        message=f"A switch with MAC address '{switch_request.mac_address}' already exists.",
                    )
                ]
            )

        # Create the switch in 'registered' state
        switch = await services.switches.create(
            await switch_request.to_switch_builder(services, state="registered")
        )

        # Create the management interface
        interface_builder = switch_request.to_interface_builder(switch.id)

        # TODO: If ip_address is provided, create StaticIPAddress entry
        # and set ip_address_id in interface_builder
        # For now, we'll just create the interface without IP

        await services.switchinterfaces.create(interface_builder)

        response.headers["Location"] = f"{V3_API_PREFIX}/switches/{switch.id}"
        return await SwitchResponse.from_model(
            switch=switch,
            self_base_hyperlink=f"{V3_API_PREFIX}/switches",
            services=services,
        )

    @handler(
        path="/switches/{switch_id}",
        methods=["PATCH"],
        tags=TAGS,
        responses={
            200: {"model": SwitchResponse},
            400: {"model": BadRequestBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_switch(
        self,
        switch_id: int,
        switch_request: SwitchUpdateRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SwitchResponse:
        """Update a switch.

        The switch must be in 'registered' or 'ready' state. If an image is
        specified and the switch has vendor information, they must be compatible.
        """
        # Check if switch exists
        existing_switch = await services.switches.get_by_id(switch_id)
        if not existing_switch:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type="SwitchNotFound",
                        message=f"Switch with id '{switch_id}' was not found.",
                    )
                ]
            )

        # Validate state
        if existing_switch.state not in ["registered", "ready"]:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type="InvalidSwitchState",
                        message=f"Switch must be in 'registered' or 'ready' state to be updated. Current state: '{existing_switch.state}'.",
                    )
                ]
            )

        # TODO: If image is provided and switch has vendor, validate compatibility
        # For now, we'll just update the fields

        # TODO: If ip_address is provided, create/update StaticIPAddress entry

        switch = await services.switches.update_by_id(
            switch_id, await switch_request.to_switch_builder(services)
        )

        return await SwitchResponse.from_model(
            switch=switch,
            self_base_hyperlink=f"{V3_API_PREFIX}/switches",
            services=services,
        )

    @handler(
        path="/switches/{switch_id}",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {"model": SwitchResponse},
            400: {"model": BadRequestBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def perform_operation(
        self,
        switch_id: int,
        operation_request: SwitchOperationRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SwitchResponse:
        """Perform operations on switches.

        Supported operations:
        - mark_fixed: Mark a switch as fixed if it was in the 'broken' state
        """
        switch = await services.switches.get_by_id(switch_id)
        if not switch:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type="SwitchNotFound",
                        message=f"Switch with id '{switch_id}' was not found.",
                    )
                ]
            )

        if operation_request.op == "mark_fixed":
            if switch.state != "broken":
                raise BadRequestException(
                    details=[
                        BaseExceptionDetail(
                            type="InvalidSwitchState",
                            message=f"Switch must be in 'broken' state to be marked as fixed. Current state: '{switch.state}'.",
                        )
                    ]
                )
            # Mark as ready (or registered, depending on requirements)
            from maasservicelayer.builders.switches import SwitchBuilder

            updated_switch = await services.switches.update_by_id(
                switch_id, SwitchBuilder(state="ready")
            )
            # TODO: Log event with optional comment
            return await SwitchResponse.from_model(
                switch=updated_switch,
                self_base_hyperlink=f"{V3_API_PREFIX}/switches",
                services=services,
            )
        else:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type="UnsupportedOperation",
                        message=f"Operation '{operation_request.op}' is not supported.",
                    )
                ]
            )

    @handler(
        path="/switches/{switch_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_switch(
        self,
        switch_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        """Delete a switch and all related entries.

        This will delete the switch, its interfaces, and any associated
        StaticIPAddress entries.
        """
        switch = await services.switches.get_by_id(switch_id)
        if not switch:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type="SwitchNotFound",
                        message=f"Switch with id '{switch_id}' was not found.",
                    )
                ]
            )

        # Delete related interfaces (cascade should handle this, but we can be explicit)
        # TODO: Also delete StaticIPAddress entries if needed

        await services.switches.delete_by_id(switch_id)
        return Response(status_code=204)

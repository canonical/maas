# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Switch`."""

from piston3.utils import rc

from maasapiserver.v3.api.public.models.requests.switches import (
    resolve_image_id,
)
from maascommon.enums.interface import InterfaceType
from maascommon.openfga.base import MAASResourceEntitlement
from maasserver.api.support import check_permission, OperationsHandler
from maasserver.exceptions import MAASAPINotFound, MAASAPIValidationError
from maasserver.sqlalchemy import service_layer
from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.interfaces import InterfaceClauseFactory
from maasservicelayer.exceptions.catalog import (
    ConflictException,
    NotFoundException,
    ValidationException,
)

DISPLAYED_SWITCH_FIELDS = ("id", "target_image_id", "target_image")


def _resolve_image_id(image: str | None) -> int | None:
    """Resolve the image name to a boot resource ID (synchronous wrapper).

    This wraps the v3 async resolve_image_id function to be called
    synchronously from the v2 API.

    Args:
        image: Image name

    Returns:
        Boot resource ID if image name is provided and found, None otherwise

    Raises:
        MAASAPIValidationError: If image name is provided but not found, or if
            short format name doesn't reference an ONIE image
    """
    try:
        return service_layer.exec_async(
            resolve_image_id(image, service_layer.services.service_collection)
        )
    except ValidationException as e:
        error_dict = {}
        if e.details:
            for detail in e.details:
                field = detail.field or "non_field_errors"
                if field not in error_dict:
                    error_dict[field] = []
                error_dict[field].append(detail.message)
        raise MAASAPIValidationError(error_dict) from None


def _switch_to_dict(switch):
    """Convert a Switch model to V2 API dictionary."""
    return {
        "id": switch.id,
        "target_image_id": switch.target_image_id,
        "target_image": getattr(switch, "target_image", None),
        "resource_uri": f"/MAAS/api/2.0/switches/{switch.id}/",
    }


class SwitchesHandler(OperationsHandler):
    """Manage switches."""

    api_doc_section_name = "Switches"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("switches_handler", [])

    def read(self, request):
        """@description-title List switches
        @description List all network switches.

        @param (int) "page" [required=false] Page number for pagination
        (default: 1).
        @param (int) "size" [required=false] Number of items per page
        (default: 20).

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        switch objects.
        @success-example "success-json" [exkey=switches-read] placeholder text
        """
        # Default pagination
        page = int(request.GET.get("page", 1))
        size = int(request.GET.get("size", 20))

        # Call V3 service layer (synchronous wrapper)
        result = service_layer.services.switches.list_with_target_image(
            page, size
        )

        return [_switch_to_dict(switch) for switch in result.items]

    @check_permission(MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES)
    def create(self, request):
        """@description-title Create a switch
        @description Create a new network switch.

        @param (string) "mac_address" [required=true] MAC address of the
        management interface.

        @param (string) "image" [required=false] Name of the target NOS image.
        Supports full format (e.g., 'onie/mellanox-3.8.0') or short format for
        ONIE images (e.g., 'mellanox-3.8.0').

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new switch
        object.
        @success-example "success-json" [exkey=switches-create] placeholder
        text

        @error (http-status-code) "400" 400
        @error (content) "bad-request" Invalid parameters.
        @error-example "bad-request"
            {"mac_address": ["This field is required."]}

        @error (http-status-code) "409" 409
        @error (content) "conflict" MAC address already assigned.
        @error-example "conflict"
            {"mac_address": ["An interface with this MAC address is already
            assigned to another entity."]}
        """
        mac_address = request.data.get("mac_address")
        image = request.data.get("image")

        if not mac_address:
            raise MAASAPIValidationError(
                {"mac_address": ["This field is required."]}
            )

        # Resolve image name to ID
        target_image_id = _resolve_image_id(image)

        # Create builder
        builder = SwitchBuilder(target_image_id=target_image_id)

        # Check for existing interface (mirroring V3 logic)
        existing_interface = service_layer.services.interfaces.get_one(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_mac_address(mac_address)
            )
        )

        try:
            if existing_interface is not None:
                if (
                    existing_interface.type == InterfaceType.UNKNOWN
                    and existing_interface.node_config_id is None
                    and existing_interface.switch_id is None
                ):
                    # Link existing UNKNOWN interface to the new switch
                    switch = service_layer.services.switches.create_switch_and_link_interface(
                        builder, existing_interface.id
                    )
                else:
                    raise MAASAPIValidationError(
                        {
                            "mac_address": [
                                f"An interface with MAC address '{mac_address}' is already assigned to another entity."
                            ]
                        }
                    )
            else:
                # Create new switch with new interface
                switch = service_layer.services.switches.create_new_switch_and_interface(
                    builder, mac_address
                )

            # Get the created switch with target image name
            switch_with_image = (
                service_layer.services.switches.get_one_with_target_image(
                    switch.id
                )
            )
            return _switch_to_dict(switch_with_image)

        except ConflictException as e:
            raise MAASAPIValidationError({"mac_address": [str(e)]}) from None


class SwitchHandler(OperationsHandler):
    """Manage a network switch."""

    api_doc_section_name = "Switch"
    create = None

    @classmethod
    def resource_uri(cls, switch=None):
        switch_id = "id"
        if switch is not None:
            switch_id = switch["id"] if isinstance(switch, dict) else switch.id
        return ("switch_handler", [switch_id])

    def read(self, request, id):
        """@description-title Read a switch
        @description Read a switch with the given ID.

        @param (int) "{id}" [required=true] A switch ID.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        switch object.
        @success-example "success-json" [exkey=switches-read-by-id] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested switch is not found.
        @error-example "not-found"
            Switch with id '42' was not found.
        """
        switch = service_layer.services.switches.get_one_with_target_image(
            int(id)
        )

        if not switch:
            raise MAASAPINotFound(f"Switch with id '{id}' was not found.")

        return _switch_to_dict(switch)

    @check_permission(MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES)
    def update(self, request, id):
        """@description-title Update switch
        @description Update a switch with the given ID.

        @param (int) "{id}" [required=true] A switch ID.

        @param (string) "image" [required=false] Name of the target NOS image.
        Supports full format (e.g., 'onie/mellanox-3.8.0') or short format for
        ONIE images (e.g., 'mellanox-3.8.0').

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        switch object.
        @success-example "success-json" [exkey=switches-update] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested switch is not found.
        @error-example "not-found"
            Switch with id '42' was not found.
        """
        # Check if switch exists
        existing_switch = (
            service_layer.services.switches.get_one_with_target_image(int(id))
        )
        if not existing_switch:
            raise MAASAPINotFound(f"Switch with id '{id}' was not found.")

        image = request.data.get("image")

        # Resolve image name to ID
        target_image_id = _resolve_image_id(image)

        # Build update
        builder = SwitchBuilder(target_image_id=target_image_id)

        try:
            switch = service_layer.services.switches.update_by_id(
                int(id), builder
            )
            # Get updated switch with target image name
            switch_with_image = (
                service_layer.services.switches.get_one_with_target_image(
                    switch.id
                )
            )
            return _switch_to_dict(switch_with_image)
        except NotFoundException:
            raise MAASAPINotFound(
                f"Switch with id '{id}' was not found."
            ) from None

    @check_permission(MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES)
    def delete(self, request, id):
        """@description-title Delete a switch
        @description Delete a switch with the given ID.

        @param (int) "{id}" [required=true] A switch ID.

        @success (http-status-code) "server-success" 204
        @success (content) "content-success" Empty response.
        @success-example "content-success"
            <no content>

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested switch is not found.
        @error-example "not-found"
            Switch with id '42' was not found.
        """
        try:
            service_layer.services.switches.delete_by_id(int(id))
            return rc.DELETED
        except NotFoundException:
            raise MAASAPINotFound(
                f"Switch with id '{id}' was not found."
            ) from None

# Copyright 2014-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Tag`."""

import http.client

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.utils import DatabaseError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from piston3.utils import rc

from maasserver.api.nodes import NODES_PREFETCH, NODES_SELECT_RELATED
from maasserver.api.support import operation, OperationsHandler
from maasserver.api.utils import (
    extract_oauth_key,
    get_list_from_dict_or_multidict,
)
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError, Unauthorized
from maasserver.forms import TagForm
from maasserver.models import (
    Device,
    Machine,
    Node,
    RackController,
    RegionController,
    Tag,
)
from maasserver.models.user import get_auth_tokens
from maasserver.permissions import NodePermission
from maasserver.utils.orm import prefetch_queryset
from provisioningserver.events import EVENT_TYPES


def check_rack_controller_access(request, rack_controller):
    """Validate API access by worker for `rack_controller`.

    This supports a rack controller accessing the update_nodes API.  If the
    request is done by anyone but the rack controller for this
    particular rack controller, the function raises :class:`PermissionDenied`.
    """
    try:
        key = extract_oauth_key(request)
    except Unauthorized as e:
        raise PermissionDenied(str(e))  # noqa: B904

    tokens = list(get_auth_tokens(rack_controller.owner))
    # Use the latest token if available
    token = tokens[-1] if tokens else None
    if token is None or key != token.key:
        raise PermissionDenied(
            "Only allowed for the %r rack controller."
            % (rack_controller.hostname)
        )


def get_tag_or_404(name, user, to_edit=False):
    """Fetch a Tag by name or raise an Http404 exception."""
    if to_edit and not user.is_superuser:
        raise PermissionDenied()
    return get_object_or_404(Tag, name=name)


class TagHandler(OperationsHandler):
    """
    Tags are properties that can be associated with a Node and serve as
    criteria for selecting and allocating nodes.

    A Tag is identified by its name.
    """

    api_doc_section_name = "Tag"
    create = None
    model = Tag
    fields = ("name", "definition", "comment", "kernel_opts")

    def read(self, request, name):
        """@description-title Read a specific tag
        @description Returns a JSON object containing information about a
        specific tag.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the requested tag.
        @success-example "success-json" [exkey=get-tag-by-name] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        return get_tag_or_404(name=name, user=request.user)

    def update(self, request, name):
        """@description-title Update a tag
        @description Update elements of a given tag.

        @param (url-string) "{name}" [required=true] The tag to update.
        @param-example "{name}" oldname
        @param (string) "name" [required=false] The new tag name. Because
        the name will be used in urls, it should be short.
        @param-example "name" virtual
        @param (string) "comment" [required=false] A description of what the
        the tag will be used for in natural language.
        @param-example "comment" The 'virtual' tag represents virtual
        machines.
        @param (string) "definition" [required=false] An XPATH query that is
        evaluated against the hardware_details stored for all nodes
        (i.e. the output of ``lshw -xml``).
        @param-example "definition"
            //node[&#64;id="display"]/'clock units="Hz"' > 1000000000

        @success (http-status-code) "200" 200
        @success (json) "success-json" A JSON tag object.
        @success-example "success-json" [exkey=update-tag] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        tag = get_tag_or_404(name=name, user=request.user, to_edit=True)
        name = tag.name
        form = TagForm(request.data, instance=tag)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        try:
            new_tag = form.save(commit=False)
            new_tag.save()
            form.save_m2m()
        except DatabaseError as e:
            raise MAASAPIValidationError(e)  # noqa: B904

        new_name = request.data.get("name")
        action = f"renamed to '{new_name}'" if new_name else "updated"
        create_audit_event(
            EVENT_TYPES.TAG,
            ENDPOINT.API,
            request,
            None,
            description=f"Tag '{name}' {action}.",
        )
        return new_tag

    def delete(self, request, name):
        """@description-title Delete a tag
        @description Deletes a tag by name.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        tag = get_tag_or_404(name=name, user=request.user, to_edit=True)
        tag.delete()
        create_audit_event(
            EVENT_TYPES.TAG,
            ENDPOINT.API,
            request,
            None,
            description=f"Tag '{tag.name}' deleted.",
        )
        return rc.DELETED

    def _get_node_type(self, model, request, name):
        # Workaround an issue where piston3 will try to use the fields from
        # this handler instead of the fields defined for the returned object.
        # This is done because this operation actually returns a list of nodes
        # and not a list of tags as this handler is defined to return.
        self.fields = None
        tag = get_tag_or_404(name=name, user=request.user)
        nodes = model.objects.get_nodes(
            request.user, NodePermission.view, from_nodes=tag.node_set.all()
        )
        nodes = nodes.select_related(*NODES_SELECT_RELATED)
        nodes = prefetch_queryset(nodes, NODES_PREFETCH).order_by("id")
        # Set related node parents so no extra queries are needed.
        for node in nodes:
            for block_device in node.current_config.blockdevice_set.all():
                block_device.node = node
        return [node.as_self() for node in nodes]

    @operation(idempotent=True)
    def nodes(self, request, name):
        """@description-title List nodes by tag
        @description Get a JSON list containing node objects that match
        the given tag name.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (json) "success-json" A JSON list containing node objects
        that match the given tag name.
        @success-example "success-json" [exkey=get-nodes-by-tag] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        return self._get_node_type(Node, request, name)

    @operation(idempotent=True)
    def machines(self, request, name):
        """@description-title List machines by tag
        @description Get a JSON list containing machine objects that match
        the given tag name.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (json) "success-json" A JSON list containing machine objects
        that match the given tag name.
        @success-example "success-json" [exkey=get-machines-by-tag] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        return self._get_node_type(Machine, request, name)

    @operation(idempotent=True)
    def devices(self, request, name):
        """@description-title List devices by tag
        @description Get a JSON list containing device objects that match
        the given tag name.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (json) "success-json" A JSON list containing device objects
        that match the given tag name.
        @success-example "success-json" [exkey=get-devices-by-tag] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        return self._get_node_type(Device, request, name)

    @operation(idempotent=True)
    def rack_controllers(self, request, name):
        """@description-title List rack controllers by tag
        @description Get a JSON list containing rack-controller objects
        that match the given tag name.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (json) "success-json" A JSON list containing rack-controller
        objects that match the given tag name.
        @success-example "success-json" [exkey=get-rackc-by-tag] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        return self._get_node_type(RackController, request, name)

    @operation(idempotent=True)
    def region_controllers(self, request, name):
        """@description-title List region controllers by tag
        @description Get a JSON list containing region-controller objects
        that match the given tag name.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (json) "success-json" A JSON list containing region-controller
        objects that match the given tag name.
        @success-example "success-json" [exkey=get-regionc-by-tag] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        return self._get_node_type(RegionController, request, name)

    def _get_nodes_for(self, request, param):
        system_ids = get_list_from_dict_or_multidict(request.data, param)
        if system_ids:
            nodes = Node.objects.filter(system_id__in=system_ids)
        else:
            nodes = Node.objects.none()
        return nodes

    @operation(idempotent=False)
    def rebuild(self, request, name):
        """@description-title Trigger a tag-node mapping rebuild
        @description Tells MAAS to rebuild the tag-to-node mappings.
        This is a maintenance operation and should not be necessary under
        normal circumstances. Adding nodes or updating a tag definition
        should automatically trigger the mapping rebuild.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @success (json) "success-json" A JSON object indicating which tag-to-
        node mapping is being rebuilt.
        @success-example "success-json" [exkey=rebuild-tag] placeholder

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        tag = get_tag_or_404(name=name, user=request.user, to_edit=True)
        tag.populate_nodes()
        return {"rebuilding": tag.name}

    @operation(idempotent=False)
    def update_nodes(self, request, name):
        """@description-title Update nodes associated with this tag
        @description Add or remove nodes associated with the given tag.
        Note that you must supply either the ``add`` or ``remove``
        parameter.

        @param (url-string) "{name}" [required=true] A tag name.
        @param-example "{name}" virtual

        @param (string) "add" [required=false] The system_id to tag.
        @param-example "add" ``fptcnd``

        @param (string) "remove" [required=false] The system_id to untag.
        @param-example "remove" ``xbpf3n``

        @param (string) "definition" [required=false] If given, the
        definition (XPATH expression) will be validated against the
        current definition of the tag. If the value does not match, MAAS
        assumes the worker is out of date and will drop the update.
        @param-example "definition"
            //node[&#64;id="display"]/'clock units="Hz"' > 1000000000

        @param (string) "rack_controller" [required=false] The system ID
        of the rack controller that processed the given tag initially.
        If not given, the requester must be a MAAS admin. If given,
        the requester must be the rack controller.

        @success (json) "success-json" A JSON object representing the
            updated node.
        @success-example "success-json" [exkey=update-nodes-tag] placeholder

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to update the nodes.
        @error-example "no-perms"
            Must be a superuser or supply a rack_controller.

        @error (http-status-code) "409" 409
        @error (content) "no-def-match" The supplied definition doesn't match
        the current definition.
        @error-example "no-def-match"
            Definition supplied 'foobar' doesn't match current definition ''

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested tag name is not found.
        @error-example "not-found"
            No Tag matches the given query.
        """
        if not request.user.is_superuser:
            raise PermissionDenied()

        tag = get_tag_or_404(name=name, user=request.user)
        definition = request.data.get("definition", None)
        if definition is not None and tag.definition != definition:
            return HttpResponse(
                "Definition supplied '%s' "
                "doesn't match current definition '%s'"
                % (definition, tag.definition),
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET
                ),
                status=int(http.client.CONFLICT),
            )
        nodes_to_add = self._get_nodes_for(request, "add")
        tag.node_set.add(*nodes_to_add)
        nodes_to_remove = self._get_nodes_for(request, "remove")
        tag.node_set.remove(*nodes_to_remove)
        return {
            "added": nodes_to_add.count(),
            "removed": nodes_to_remove.count(),
        }

    @classmethod
    def resource_uri(cls, tag=None):
        # See the comment in NodeHandler.resource_uri
        tag_name = "name"
        if tag is not None:
            tag_name = tag.name
        return ("tag_handler", (tag_name,))


class TagsHandler(OperationsHandler):
    """Manage all tags known to MAAS."""

    api_doc_section_name = "Tags"
    update = delete = None

    def create(self, request):
        """@description-title Create a new tag
        @description Create a new tag.

        @param (string) "name" [required=true] The new tag name. Because
        the name will be used in urls, it should be short.
        @param-example "name" virtual
        @param (string) "comment" [required=false] A description of what the
        the tag will be used for in natural language.
        @param-example "comment" The 'virtual' tag represents virtual
        machines.
        @param (string) "definition" [required=false] An XPATH query that is
        evaluated against the hardware_details stored for all nodes
        (i.e. the output of ``lshw -xml``).
        @param-example "definition"
            //node[&#64;id="display"]/'clock units="Hz"' > 1000000000
        @param (string) "kernel_opts" [required=false] Nodes associated
        with this tag will add this string to their kernel options
        when booting. The value overrides the global ``kernel_opts``
        setting. If more than one tag is associated with a node, command
        line will be concatenated from all associated tags, in alphabetic
        tag name order.
        @param-example "kernel_opts"
            nouveau.noaccel=1

        @success (json) "success-json" A JSON object representing the
        new tag.
        @success-example "success-json" [exkey=add-tag] placeholder

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have the permissions
        required to create a tag.
        @error-example "no-perms"
            No content
        """
        if not request.user.is_superuser:
            raise PermissionDenied()

        form = TagForm(request.data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        tag = form.save()
        create_audit_event(
            EVENT_TYPES.TAG,
            ENDPOINT.API,
            request,
            None,
            description=f"Tag '{tag.name}' created.",
        )
        return tag

    def read(self, request):
        """@description-title List tags
        @description Outputs a JSON object containing an array of all
        currently defined tag objects.

        @success (json) "success-json" A JSON object containing an array
        of all currently defined tag objects.
        @success-example "success-json" [exkey=get-tags] placeholder
        """
        return Tag.objects.all()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("tags_handler", [])

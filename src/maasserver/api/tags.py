# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Tag`."""

__all__ = [
    'TagHandler',
    'TagsHandler',
    ]


import http.client

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.utils import DatabaseError
from django.http import HttpResponse
from maasserver.api.nodes import (
    NODES_PREFETCH,
    NODES_SELECT_RELATED,
)
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    extract_oauth_key,
    get_list_from_dict_or_multidict,
)
from maasserver.exceptions import (
    MAASAPIValidationError,
    Unauthorized,
)
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
from maasserver.utils.orm import (
    get_one,
    prefetch_queryset,
)
from piston3.utils import rc


def check_rack_controller_access(request, rack_controller):
    """Validate API access by worker for `rack_controller`.

    This supports a rack controller accessing the update_nodes API.  If the
    request is done by anyone but the rack controller for this
    particular rack controller, the function raises :class:`PermissionDenied`.
    """
    try:
        key = extract_oauth_key(request)
    except Unauthorized as e:
        raise PermissionDenied(str(e))

    tokens = list(get_auth_tokens(rack_controller.owner))
    if len(tokens) > 0:
        # Use the latest token.
        token = tokens[-1]
    else:
        token = None
    if key != token.key:
        raise PermissionDenied(
            "Only allowed for the %r rack controller." % (
                rack_controller.hostname))


class TagHandler(OperationsHandler):
    """Manage a Tag.

    Tags are properties that can be associated with a Node and serve as
    criteria for selecting and allocating nodes.

    A Tag is identified by its name.
    """
    api_doc_section_name = "Tag"
    create = None
    model = Tag
    fields = (
        'name',
        'definition',
        'comment',
        'kernel_opts',
        )

    def read(self, request, name):
        """Read a specific Tag.

        Returns 404 if the tag is not found.
        """
        return Tag.objects.get_tag_or_404(name=name, user=request.user)

    def update(self, request, name):
        """Update a specific Tag.

        :param name: The name of the Tag to be created. This should be a short
            name, and will be used in the URL of the tag.
        :param comment: A long form description of what the tag is meant for.
            It is meant as a human readable description of the tag.
        :param definition: An XPATH query that will be evaluated against the
            hardware_details stored for all nodes (output of `lshw -xml`).

        Returns 404 if the tag is not found.
        """
        tag = Tag.objects.get_tag_or_404(
            name=name, user=request.user, to_edit=True)
        form = TagForm(request.data, instance=tag)
        if form.is_valid():
            try:
                new_tag = form.save(commit=False)
                new_tag.save()
                form.save_m2m()
            except DatabaseError as e:
                raise MAASAPIValidationError(e)
            return new_tag
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, name):
        """Delete a specific Tag.

        Returns 404 if the tag is not found.
        Returns 204 if the tag is successfully deleted.
        """
        tag = Tag.objects.get_tag_or_404(
            name=name, user=request.user, to_edit=True)
        tag.delete()
        return rc.DELETED

    def _get_node_type(self, model, request, name):
        # Workaround an issue where piston3 will try to use the fields from
        # this handler instead of the fields defined for the returned object.
        # This is done because this operation actually returns a list of nodes
        # and not a list of tags as this handler is defined to return.
        self.fields = None
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user)
        nodes = model.objects.get_nodes(
            request.user, NodePermission.view,
            from_nodes=tag.node_set.all())
        nodes = nodes.select_related(*NODES_SELECT_RELATED)
        nodes = prefetch_queryset(nodes, NODES_PREFETCH).order_by('id')
        # Set related node parents so no extra queries are needed.
        for node in nodes:
            for interface in node.interface_set.all():
                interface.node = node
            for block_device in node.blockdevice_set.all():
                block_device.node = node
        return [
            node.as_self()
            for node in nodes
        ]

    @operation(idempotent=True)
    def nodes(self, request, name):
        """Get the list of nodes that have this tag.

        Returns 404 if the tag is not found.
        """
        return self._get_node_type(Node, request, name)

    @operation(idempotent=True)
    def machines(self, request, name):
        """Get the list of machines that have this tag.

        Returns 404 if the tag is not found.
        """
        return self._get_node_type(Machine, request, name)

    @operation(idempotent=True)
    def devices(self, request, name):
        """Get the list of devices that have this tag.

        Returns 404 if the tag is not found.
        """
        return self._get_node_type(Device, request, name)

    @operation(idempotent=True)
    def rack_controllers(self, request, name):
        """Get the list of rack controllers that have this tag.

        Returns 404 if the tag is not found.
        """
        return self._get_node_type(RackController, request, name)

    @operation(idempotent=True)
    def region_controllers(self, request, name):
        """Get the list of region controllers that have this tag.

        Returns 404 if the tag is not found.
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
        """Manually trigger a rebuild the tag <=> node mapping.

        This is considered a maintenance operation, which should normally not
        be necessary. Adding nodes or updating a tag's definition should
        automatically trigger the appropriate changes.

        Returns 404 if the tag is not found.
        """
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user,
                                         to_edit=True)
        tag.populate_nodes()
        return {'rebuilding': tag.name}

    @operation(idempotent=False)
    def update_nodes(self, request, name):
        """Add or remove nodes being associated with this tag.

        :param add: system_ids of nodes to add to this tag.
        :param remove: system_ids of nodes to remove from this tag.
        :param definition: (optional) If supplied, the definition will be
            validated against the current definition of the tag. If the value
            does not match, then the update will be dropped (assuming this was
            just a case of a worker being out-of-date)
        :param rack_controller: A system ID of a rack controller that did the
            processing. This value is optional. If not supplied, the requester
            must be a superuser. If supplied, then the requester must be the
            rack controller.

        Returns 404 if the tag is not found.
        Returns 401 if the user does not have permission to update the nodes.
        Returns 409 if 'definition' doesn't match the current definition.
        """
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user)
        rack_controller = None
        if not request.user.is_superuser:
            system_id = request.data.get('rack_controller', None)
            if system_id is None:
                raise PermissionDenied(
                    'Must be a superuser or supply a rack_controller')
            rack_controller = get_one(
                RackController.objects.filter(system_id=system_id))
            check_rack_controller_access(request, rack_controller)
        definition = request.data.get('definition', None)
        if definition is not None and tag.definition != definition:
            return HttpResponse(
                "Definition supplied '%s' "
                "doesn't match current definition '%s'"
                % (definition, tag.definition),
                content_type=(
                    "text/plain; charset=%s" % settings.DEFAULT_CHARSET),
                status=int(http.client.CONFLICT))
        nodes_to_add = self._get_nodes_for(request, 'add')
        tag.node_set.add(*nodes_to_add)
        nodes_to_remove = self._get_nodes_for(request, 'remove')
        tag.node_set.remove(*nodes_to_remove)
        return {
            'added': nodes_to_add.count(),
            'removed': nodes_to_remove.count()
            }

    @classmethod
    def resource_uri(cls, tag=None):
        # See the comment in NodeHandler.resource_uri
        tag_name = 'name'
        if tag is not None:
            tag_name = tag.name
        return ('tag_handler', (tag_name, ))


class TagsHandler(OperationsHandler):
    """Manage the collection of all the Tags in this MAAS."""
    api_doc_section_name = "Tags"
    update = delete = None

    def create(self, request):
        """Create a new Tag.

        :param name: The name of the Tag to be created. This should be a short
            name, and will be used in the URL of the tag.
        :param comment: A long form description of what the tag is meant for.
            It is meant as a human readable description of the tag.
        :param definition: An XPATH query that will be evaluated against the
            hardware_details stored for all nodes (output of `lshw -xml`).
        :param kernel_opts: Can be None. If set, nodes associated with this tag
            will add this string to their kernel options when booting. The
            value overrides the global 'kernel_opts' setting. If more than one
            tag is associated with a node, the one with the lowest alphabetical
            name will be picked (eg 01-my-tag will be taken over 99-tag-name).

        Returns 401 if the user is not an admin.
        """
        if not request.user.is_superuser:
            raise PermissionDenied()
        form = TagForm(request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def read(self, request):
        """List Tags.

        Get a listing of all tags that are currently defined.
        """
        return Tag.objects.all()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('tags_handler', [])

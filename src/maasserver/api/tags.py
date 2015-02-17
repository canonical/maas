# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Tag`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'TagHandler',
    'TagsHandler',
    ]


import httplib

from django.core.exceptions import PermissionDenied
from django.db.utils import DatabaseError
from django.http import HttpResponse
from maasserver.api.nodegroups import check_nodegroup_access
from maasserver.api.support import (
    operation,
    OperationsHandler,
    )
from maasserver.api.utils import get_list_from_dict_or_multidict
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import TagForm
from maasserver.models import (
    Node,
    NodeGroup,
    Tag,
    )
from maasserver.utils.orm import get_one
from piston.utils import rc


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

    @operation(idempotent=True)
    def nodes(self, request, name):
        """Get the list of nodes that have this tag.

        Returns 404 if the tag is not found.
        """
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user)
        return Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, from_nodes=tag.node_set.all())

    def _get_nodes_for(self, request, param, nodegroup):
        system_ids = get_list_from_dict_or_multidict(request.data, param)
        if system_ids:
            nodes = Node.objects.filter(system_id__in=system_ids)
            if nodegroup is not None:
                nodes = nodes.filter(nodegroup=nodegroup)
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
        :param nodegroup: A uuid of a nodegroup being processed. This value is
            optional. If not supplied, the requester must be a superuser. If
            supplied, then the requester must be the worker associated with
            that nodegroup, and only nodes that are part of that nodegroup can
            be updated.

        Returns 404 if the tag is not found.
        Returns 401 if the user does not have permission to update the nodes.
        Returns 409 if 'definition' doesn't match the current definition.
        """
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user)
        nodegroup = None
        if not request.user.is_superuser:
            uuid = request.data.get('nodegroup', None)
            if uuid is None:
                raise PermissionDenied(
                    'Must be a superuser or supply a nodegroup')
            nodegroup = get_one(NodeGroup.objects.filter(uuid=uuid))
            check_nodegroup_access(request, nodegroup)
        definition = request.data.get('definition', None)
        if definition is not None and tag.definition != definition:
            return HttpResponse(
                "Definition supplied '%s' "
                "doesn't match current definition '%s'"
                % (definition, tag.definition),
                status=httplib.CONFLICT)
        nodes_to_add = self._get_nodes_for(request, 'add', nodegroup)
        tag.node_set.add(*nodes_to_add)
        nodes_to_remove = self._get_nodes_for(request, 'remove', nodegroup)
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
    create = read = update = delete = None

    @operation(idempotent=False)
    def new(self, request):
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

    @operation(idempotent=True)
    def list(self, request):
        """List Tags.

        Get a listing of all tags that are currently defined.
        """
        return Tag.objects.all()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('tags_handler', [])

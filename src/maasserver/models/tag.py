# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "Tag",
    ]

from django.core.exceptions import (
    PermissionDenied,
    )
from django.db.models import (
    CharField,
    Manager,
    TextField,
    )
from django.shortcuts import get_object_or_404
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


# Permission model for tags. Everyone can see all tags, but only superusers can
# edit tags.
class TagManager(Manager):
    """A utility to manage the collection of Tags."""

    def get_tag_or_404(self, name, user, to_edit=False):
        """Fetch a `Tag` by name.  Raise exceptions if no `Tag` with
        this name exist.

        :param name: The Tag.name.
        :type name: str
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param to_edit: Are we going to edit this tag, or just view it?
        :type to_edit: bool
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        if to_edit and not user.is_superuser:
            raise PermissionDenied()
        tag = get_object_or_404(Tag, name=name)
        return tag


class Tag(CleanSave, TimestampedModel):
    """A `Tag` is a label applied to a `Node`.

    :ivar name: The short-human-identifiable name for this tag.
    :ivar definition: The XPATH string identifying what nodes should match this
        tag.
    :ivar comment: A long-form description for humans about what this tag is
        trying to accomplish.
    :ivar objects: The :class:`TagManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    name = CharField(max_length=256, unique=True, editable=True)
    definition = TextField()
    comment = TextField(blank=True)

    objects = TagManager()

    def __unicode__(self):
        return self.name

    def populate_nodes(self):
        """Find all nodes that match this tag, and update them."""
        # Local import to avoid circular reference
        from maasserver.models import Node
        # First destroy the existing tags
        self.node_set.clear()
        # Now figure out what matches the new definition
        for node in Node.objects.raw(
                'SELECT id FROM maasserver_node'
                ' WHERE xpath_exists(%s, hardware_details)',
                [self.definition]):
            # Is there an efficiency difference between doing
            # 'node.tags.add(self)' and 'self.node_set.add(node)' ?
            node.tags.add(self)

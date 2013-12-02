# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Tag",
    ]

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
    TextField,
    )
from django.shortcuts import get_object_or_404
from lxml import etree
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class TagManager(Manager):
    """A utility to manage the collection of Tags."""
    # Everyone can see all tags, but only superusers can edit tags.

    def get_tag_or_404(self, name, user, to_edit=False):
        """Fetch a `Tag` by name.  Raise exceptions if no `Tag` with
        this name exist.

        :param name: The Tag.name.
        :type name: string
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
        return get_object_or_404(Tag, name=name)


class Tag(CleanSave, TimestampedModel):
    """A `Tag` is a label applied to a `Node`.

    :ivar name: The short-human-identifiable name for this tag.
    :ivar definition: The XPATH string identifying what nodes should match this
        tag.
    :ivar comment: A long-form description for humans about what this tag is
        trying to accomplish.
    :ivar kernel_opts: Optional kernel command-line parameters string to be
        used in the PXE config for nodes with this tags.
    :ivar objects: The :class:`TagManager`.
    """

    _tag_name_regex = '^[\w-]+$'

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    name = CharField(max_length=256, unique=True, editable=True,
                     validators=[RegexValidator(_tag_name_regex)])
    definition = TextField(blank=True)
    comment = TextField(blank=True)
    kernel_opts = TextField(blank=True, null=True)

    objects = TagManager()

    def __init__(self, *args, **kwargs):
        super(Tag, self).__init__(*args, **kwargs)
        # Track what the original definition is, so we can detect when it
        # changes and we need to repopulate the node<=>tag mapping.
        # We have to check for self.id, otherwise we don't see the creation of
        # a new definition.
        if self.id is None:
            self._original_definition = None
        else:
            self._original_definition = self.definition

    def __unicode__(self):
        return self.name

    def populate_nodes(self):
        """Find all nodes that match this tag, and update them."""
        from maasserver.populate_tags import populate_tags
        if not self.is_defined:
            return
        # before we pass off any work, ensure the definition is valid XPATH
        try:
            etree.XPath(self.definition)
        except etree.XPathSyntaxError as e:
            msg = 'Invalid xpath expression: %s' % (e,)
            raise ValidationError({'definition': [msg]})
        # Now delete the existing tags
        self.node_set.clear()
        populate_tags(self)

    def save(self, *args, **kwargs):
        super(Tag, self).save(*args, **kwargs)
        if self.definition != self._original_definition:
            self.populate_nodes()
        self._original_definition = self.definition

    @property
    def is_defined(self):
        return (
            self.definition is not None and
            self.definition != "" and
            not self.definition.isspace()
        )

# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Definition of the Tag data model."""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import CharField, TextField
from lxml import etree
from temporalio.common import WorkflowIDReusePolicy
from twisted.internet import reactor

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.workflow import start_workflow
from maastemporalworker.workflow.tag_evaluation import TagEvaluationParam
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("tag")


class Tag(CleanSave, TimestampedModel):
    """A `Tag` is a label applied to a `Node`.

    :ivar name: The short-human-identifiable name for this tag.
    :ivar definition: The XPATH string identifying what nodes should match this
        tag.
    :ivar comment: A long-form description for humans about what this tag is
        trying to accomplish.
    :ivar kernel_opts: Optional kernel command-line parameters string to be
        used in the PXE config for nodes with this tag.
    :ivar objects: The :class:`TagManager`.
    """

    _tag_name_regex = "^[a-zA-Z0-9_-]+$"

    name = CharField(
        max_length=256,
        unique=True,
        editable=True,
        validators=[RegexValidator(_tag_name_regex)],
    )
    definition = TextField(blank=True)
    comment = TextField(blank=True)
    kernel_opts = TextField(blank=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track what the original definition is, so we can detect when it
        # changes and we need to repopulate the node<=>tag mapping.
        # We have to check for self.id, otherwise we don't see the creation of
        # a new definition.
        if self.id is None:
            self._original_definition = None
        else:
            self._original_definition = self.definition

    def __str__(self):
        return self.name

    @property
    def is_defined(self):
        return bool(self.definition.strip())

    def clean(self):
        self.clean_definition()

    def clean_definition(self):
        if self.is_defined:
            try:
                etree.XPath(self.definition)
            except etree.XPathSyntaxError as e:
                msg = f"Invalid XPath expression: {e}"
                raise ValidationError({"definition": [msg]})

    def save(self, *args, populate=True, **kwargs):
        """Save this tag.

        :param populate: Whether to call `populate_nodes` if the definition has
            changed.
        """
        super().save(*args, **kwargs)
        maaslog.info("Tag (id=%d) has been saved.", self.id)

        if populate and (self.definition != self._original_definition):
            self.populate_nodes()
        self._original_definition = self.definition

    def populate_nodes(self):
        """Find all nodes that match this tag, and update them.

        By default, node population is deferred.
        """
        return self._populate_nodes_later()

    def _populate_nodes_later(self):
        """Find all nodes that match this tag, and update them, later.

        This schedules population to happen without waiting for its outcome.
        """
        if self.is_defined:
            # This thread does not wait for it to complete.
            reactor.callLater(0, self._update_tag_node_relations)

    def _update_tag_node_relations(self) -> None:
        """
        Evaluate a tag searching for matches between the tag provided and the
        nodes in MAAS.
        """
        maaslog.info(
            "Tag (id=%d) is being evaluated against all nodes.", self.id
        )
        param = TagEvaluationParam(self.id, self.definition)

        start_workflow(
            workflow_name="tag-evaluation",
            workflow_id="tag-evaluation",
            task_queue="region",
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            param=param,
        )

    def _populate_nodes_now(self):
        """Find all nodes that match this tag, and update them, now.

        All computation will be done within the current transaction, within
        the current thread. This could be costly.
        """
        # Avoid circular imports.
        from maasserver.models.node import Node
        from maasserver.populate_tags import populate_tag_for_multiple_nodes

        if self.is_defined:
            # Do the work here and now in this thread. This is probably a
            # terrible mistake... unless you're testing.
            populate_tag_for_multiple_nodes(self, Node.objects.all())

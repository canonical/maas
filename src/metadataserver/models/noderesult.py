# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`NodeResult` model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NodeResult',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    )
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.converters import XMLToYAML
from metadataserver import DefaultMeta
from metadataserver.enum import (
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
    )
from metadataserver.fields import BinaryField


class NodeResultManager(Manager):
    """Utility to manage a collection of :class:`NodeResult`s."""

    def clear_results(self, node):
        """Remove all existing results for a node."""
        self.filter(node=node).delete()

    def store_data(self, node, name, script_result, result_type, data):
        """Store data about a node.

        :param node: The node that this result pertains to.
        :type node: :class:`maasserver.models.Node`

        :param name: The name of this result, typically the name of
            the commissioning script that generated it.
        :type name: string

        :param script_result: The exit code of the commissioning
            script.
        :type script_result: int

        :param result_type: The enum value for either commissioning (0)
            or installing (1).
        :type script_result: int

        :param data: The raw binary output of the commissioning
            script.
        :type data: :class:`metadataserver.fields.Bin`

        """
        existing, created = self.get_or_create(
            node=node, name=name,
            defaults=dict(
                script_result=script_result, result_type=result_type,
                data=data))
        if not created:
            existing.script_result = script_result
            existing.result_type = result_type
            existing.data = data
            existing.save()
        return existing

    def get_data(self, node, name):
        """Get data about a node."""
        ncr = get_object_or_404(NodeResult, node=node, name=name)
        return ncr.data


class NodeResult(CleanSave, TimestampedModel):
    """Storage for data returned from node commissioning/installing.

    Commissioning/Installing a node results in various bits of data that
    need to be stored, such as lshw output.  This model allows storing of
    this data as unicode text, with an arbitrary name, for later retrieval.

    :ivar node: The context :class:`Node`.
    :ivar script_result: If this data results from the execution of a script,
        this is the status of this execution.  This can be "OK", "FAILED" or
        "WORKING" for progress reports.
    :ivar result_type: This can be either commissioning or installing.
    :ivar name: A unique name to use for the data being stored.
    :ivar data: The file's actual data, unicode only.
    """

    class Meta(DefaultMeta):
        unique_together = ('node', 'name')

    objects = NodeResultManager()

    node = ForeignKey(
        'maasserver.Node', null=False, editable=False, unique=False)
    script_result = IntegerField(editable=False)
    result_type = IntegerField(
        choices=RESULT_TYPE_CHOICES, editable=False,
        default=RESULT_TYPE.COMMISSIONING)
    name = CharField(max_length=255, unique=False, editable=False)
    data = BinaryField(
        max_length=1024 * 1024, editable=True, blank=True, default=b'',
        null=False)

    def __unicode__(self):
        return "%s/%s" % (self.node.system_id, self.name)

    def get_data_as_html(self):
        """More-or-less human-readable HTML representation of the output."""
        return escape(self.data.decode('utf-8', 'replace'))

    def get_data_as_yaml_html(self):
        """More-or-less human-readable Yaml HTML representation
        of the output.
        """
        from metadataserver.models.commissioningscript import (
            LLDP_OUTPUT_NAME,
            LSHW_OUTPUT_NAME,
        )
        if self.name in (LLDP_OUTPUT_NAME, LSHW_OUTPUT_NAME):
            return escape(XMLToYAML(self.data).convert())

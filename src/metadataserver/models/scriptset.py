# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "ScriptSet",
]

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import (
    CASCADE,
    DateTimeField,
    ForeignKey,
    IntegerField,
    Model,
)
from maasserver.models.cleansave import CleanSave
from metadataserver.enum import (
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
)


class ScriptSet(CleanSave, Model):

    last_ping = DateTimeField(blank=True, null=True)

    node = ForeignKey('maasserver.Node', on_delete=CASCADE)

    result_type = IntegerField(
        choices=RESULT_TYPE_CHOICES, editable=False,
        default=RESULT_TYPE.COMMISSIONING)

    def __str__(self):
        return "%s/%s" % (
            self.node.system_id, RESULT_TYPE_CHOICES[self.result_type][1])

    def __iter__(self):
        for script_result in self.scriptresult_set.all():
            yield script_result

    def find_script_result(self, script_result_id=None, script_name=None):
        """Find a script result in the current set."""
        if script_result_id is not None:
            try:
                return self.scriptresult_set.get(id=script_result_id)
            except ObjectDoesNotExist:
                pass
        else:
            for script_result in self:
                if script_result.name == script_name:
                    return script_result
        return None

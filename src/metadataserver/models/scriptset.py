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
    Manager,
    Model,
)
from maasserver.models.cleansave import CleanSave
from maasserver.preseed import CURTIN_INSTALL_LOG
from metadataserver.enum import (
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
    SCRIPT_STATUS,
    SCRIPT_TYPE,
)
from metadataserver.models.script import Script
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS


class ScriptSetManager(Manager):

    def create_commissioning_script_set(self, node):
        """Create a new commissioning ScriptSet with ScriptResults

        ScriptResults will be created for all builtin commissioning scripts
        and custom commissioning scripts if the node is not a controller.
        """
        # Avoid circular dependencies.
        from metadataserver.models import ScriptResult

        script_set = self.create(
            node=node, result_type=RESULT_TYPE.COMMISSIONING)

        for script_name, data in NODE_INFO_SCRIPTS.items():
            if node.is_controller and not data['run_on_controller']:
                continue
            ScriptResult.objects.create(
                script_set=script_set, status=SCRIPT_STATUS.PENDING,
                script_name=script_name)

        # MAAS doesn't run custom commissioning scripts during controller
        # refresh.
        if node.is_controller:
            return script_set

        for script in Script.objects.filter(
                script_type=SCRIPT_TYPE.COMMISSIONING):
            ScriptResult.objects.create(
                script_set=script_set, status=SCRIPT_STATUS.PENDING,
                script=script, script_version=script.script)

        return script_set

    def create_testing_script_set(self, node):
        """Create a new testing ScriptSet with ScriptResults."""
        # Avoid circular dependencies.
        from metadataserver.models import ScriptResult

        script_set = self.create(node=node, result_type=RESULT_TYPE.TESTING)

        for script in Script.objects.filter(script_type=SCRIPT_TYPE.TESTING):
            ScriptResult.objects.create(
                script_set=script_set, status=SCRIPT_STATUS.PENDING,
                script=script, script_version=script.script)

        return script_set

    def create_installation_script_set(self, node):
        """Create a new installation ScriptSet with a ScriptResult."""
        # Avoid circular dependencies.
        from metadataserver.models import ScriptResult

        script_set = self.create(
            node=node, result_type=RESULT_TYPE.INSTALLATION)
        # Curtin uploads the installation log using the full path we specify in
        # the preseed.
        ScriptResult.objects.create(
            script_set=script_set, status=SCRIPT_STATUS.PENDING,
            script_name=CURTIN_INSTALL_LOG)
        return script_set


class ScriptSet(CleanSave, Model):

    objects = ScriptSetManager()

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

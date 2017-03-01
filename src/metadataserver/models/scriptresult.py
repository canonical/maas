# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
__all__ = [
    'ScriptResult',
    ]


from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    IntegerField,
    SET_NULL,
)
from maasserver.fields import JSONObjectField
from maasserver.models.cleansave import CleanSave
from maasserver.models.event import Event
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.versionedtextfile import VersionedTextFile
from metadataserver import (
    DefaultMeta,
    logger,
)
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
)
from metadataserver.fields import (
    Bin,
    BinaryField,
)
from metadataserver.models.commissioningscript import NODE_INFO_SCRIPTS
from metadataserver.models.script import Script
from metadataserver.models.scriptset import ScriptSet
from provisioningserver.events import EVENT_TYPES


class ScriptResult(CleanSave, TimestampedModel):

    # Force model into the metadataserver namespace.
    class Meta(DefaultMeta):
        pass

    script_set = ForeignKey(ScriptSet, editable=False, on_delete=CASCADE)

    # All ScriptResults except commissioning scripts will be linked to a Script
    # as commissioning scripts are still embedded in the MAAS source.
    script = ForeignKey(
        Script, editable=False, blank=True, null=True, on_delete=SET_NULL)

    script_version = ForeignKey(
        VersionedTextFile, blank=True, null=True, editable=False,
        on_delete=SET_NULL)

    status = IntegerField(
        choices=SCRIPT_STATUS_CHOICES, default=SCRIPT_STATUS.PENDING)

    exit_status = IntegerField(blank=True, null=True)

    # Only used by the builtin commissioning scripts and installation result.
    script_name = CharField(
        max_length=255, unique=False, editable=False, null=True)

    output = BinaryField(max_length=1024 * 1024, blank=True, default=b'')

    stdout = BinaryField(max_length=1024 * 1024, blank=True, default=b'')

    stderr = BinaryField(max_length=1024 * 1024, blank=True, default=b'')

    # If a result is given in the output convert it to JSON and store it here.
    result = JSONObjectField(blank=True, default='')

    @property
    def name(self):
        if self.script is not None:
            return self.script.name
        elif self.script_name is not None:
            return self.script_name
        else:
            return "Unknown"

    @property
    def status_name(self):
        return SCRIPT_STATUS_CHOICES[self.status][1]

    def __str__(self):
        return "%s/%s" % (self.script_set.node.system_id, self.name)

    def store_result(
            self, exit_status, output=None, stdout=None, stderr=None,
            result=None, script_version_id=None):
        # Don't allow ScriptResults to be overwritten unless the node is a
        # controller. Controllers are allowed to overwrite their results to
        # prevent new ScriptSets being created everytime a controller starts.
        # This also allows us to avoid creating an RPC call for the rack
        # controller to create a new ScriptSet.
        if not self.script_set.node.is_controller:
            # Allow both PENDING and RUNNING scripts incase the node didn't
            # inform MAAS the Script was being run, it just uploaded results.
            assert self.status in (
                SCRIPT_STATUS.PENDING, SCRIPT_STATUS.RUNNING)
            assert self.output == b''
            assert self.stdout == b''
            assert self.stderr == b''
            assert self.result == ''
            assert self.script_version is None

        self.exit_status = exit_status
        if exit_status == 0:
            self.status = SCRIPT_STATUS.PASSED
        else:
            self.status = SCRIPT_STATUS.FAILED
        if output is not None:
            self.output = Bin(output)
        if stdout is not None:
            self.stdout = Bin(stdout)
        if stderr is not None:
            self.stderr = Bin(stderr)
        if result is not None:
            self.result = result
        if self.script:
            if script_version_id is not None:
                for script in self.script.script.previous_versions():
                    if script.id == script_version_id:
                        self.script_version = script
                        break
                if self.script_version is None:
                    err_msg = (
                        "%s(%s) sent a script result for %s(%d) with an "
                        "unknown script version(%d)." % (
                            self.script_set.node.fqdn,
                            self.script_set.node.system_id,
                            self.script.name, self.script.id,
                            script_version_id))
                    logger.error(err_msg)
                    Event.objects.create_node_event(
                        system_id=self.script_set.node.system_id,
                        event_type=EVENT_TYPES.SCRIPT_RESULT_ERROR,
                        event_description=err_msg)
            else:
                # If no script version was given assume the latest version
                # was run.
                self.script_version = self.script.script

        # If commissioning result check if its a builtin script, if so run its
        # hook before committing to the database.
        if (self.script_set.result_type == RESULT_TYPE.COMMISSIONING and
                self.name in NODE_INFO_SCRIPTS):
            post_process_hook = NODE_INFO_SCRIPTS[self.name]['hook']
            post_process_hook(
                node=self.script_set.node, output=self.stdout,
                exit_status=self.exit_status)

        self.save()

# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CASCADE,
    CharField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    JSONField,
    Q,
    SET_NULL,
)
import yaml

from maasserver.models.cleansave import CleanSave
from maasserver.models.event import Event
from maasserver.models.interface import Interface
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.timestampedmodel import now, TimestampedModel
from maasserver.models.versionedtextfile import VersionedTextFile
from metadataserver import logger
from metadataserver.builtin_scripts.hooks import NODE_INFO_SCRIPTS
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
    SCRIPT_STATUS_RUNNING_OR_PENDING,
    SCRIPT_TYPE,
)
from metadataserver.fields import Bin, BinaryField
from metadataserver.models.script import Script
from metadataserver.models.scriptset import ScriptSet
from provisioningserver.events import EVENT_TYPES


class ScriptResult(CleanSave, TimestampedModel):
    script_set = ForeignKey(ScriptSet, editable=False, on_delete=CASCADE)

    # All ScriptResults except commissioning scripts will be linked to a Script
    # as commissioning scripts are still embedded in the MAAS source.
    script = ForeignKey(
        Script, editable=False, blank=True, null=True, on_delete=CASCADE
    )

    # Any parameters set by MAAS or the user which should be passed to the
    # running script.
    parameters = JSONField(blank=True, default=dict)

    # If the result is in reference to a particular block device link it.
    physical_blockdevice = ForeignKey(
        PhysicalBlockDevice,
        editable=False,
        blank=True,
        null=True,
        on_delete=CASCADE,
    )

    # If the result is in reference to a particular Interface link it.
    interface = ForeignKey(
        Interface, editable=False, blank=True, null=True, on_delete=CASCADE
    )

    script_version = ForeignKey(
        VersionedTextFile,
        blank=True,
        null=True,
        editable=False,
        on_delete=SET_NULL,
    )

    status = IntegerField(
        choices=SCRIPT_STATUS_CHOICES, default=SCRIPT_STATUS.PENDING
    )

    exit_status = IntegerField(blank=True, null=True)

    # Used by the builtin commissioning scripts and installation result. Also
    # stores the Script name incase the Script is deleted but the result isn't.
    script_name = CharField(
        max_length=255, unique=False, editable=False, null=True
    )

    output = BinaryField(max_length=1024 * 1024, blank=True, default=b"")

    stdout = BinaryField(max_length=1024 * 1024, blank=True, default=b"")

    stderr = BinaryField(max_length=1024 * 1024, blank=True, default=b"")

    result = BinaryField(max_length=1024 * 1024, blank=True, default=b"")

    # When the script started to run
    started = DateTimeField(editable=False, null=True, blank=True)

    # When the script finished running
    ended = DateTimeField(editable=False, null=True, blank=True)

    # Whether or not the failed script result should be suppressed.
    suppressed = BooleanField(default=False)

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

    @property
    def runtime(self):
        if None not in (self.ended, self.started):
            runtime = self.ended - self.started
            return str(runtime - timedelta(microseconds=runtime.microseconds))
        else:
            return ""

    @property
    def starttime(self):
        if self.started is not None:
            return self.started.timestamp()
        else:
            return ""

    @property
    def endtime(self):
        if self.ended is not None:
            return self.ended.timestamp()
        else:
            return ""

    @property
    def estimated_runtime(self):
        # If there is a runtime the script has completed, no need to calculate
        # an estimate.
        if self.runtime != "":
            return self.runtime
        runtime = None
        # Get an estimated runtime from previous runs.
        for script_result in self.history.only(
            "status",
            "started",
            "ended",
            "script_id",
            "script_name",
            "script_set_id",
            "physical_blockdevice_id",
            "created",
        ):
            # Only look at passed results when calculating an estimated
            # runtime. Failed results may take longer or shorter than
            # average. Don't use self.history.filter for this as the now
            # cached history list may be used elsewhere.
            if script_result.status != SCRIPT_STATUS.PASSED:
                continue
            # LP: #1730799 - Old results may not have started set.
            if script_result.started is None:
                script_result.started = script_result.ended
                script_result.save(update_fields=["started"])
            previous_runtime = script_result.ended - script_result.started
            if runtime is None:
                runtime = previous_runtime
            else:
                runtime += previous_runtime
                runtime = runtime / 2
        if runtime is None:
            if self.script is not None and self.script.timeout != timedelta(0):
                # If there were no previous runs use the script's timeout.
                return str(
                    self.script.timeout
                    - timedelta(microseconds=self.script.timeout.microseconds)
                )
            else:
                return "Unknown"
        else:
            return str(runtime - timedelta(microseconds=runtime.microseconds))

    def __str__(self):
        return f"{self.script_set.node.system_id}/{self.name}"

    def read_results(self):
        """Read the results YAML file and validate it."""
        try:
            parsed_yaml = yaml.safe_load(self.result)
        except yaml.YAMLError as err:
            raise ValidationError(err)

        if parsed_yaml is None:
            # No results were given.
            return {}
        elif not isinstance(parsed_yaml, dict):
            raise ValidationError("YAML must be a dictionary.")

        if parsed_yaml.get("status") not in [
            "passed",
            "failed",
            "degraded",
            "timedout",
            "skipped",
            None,
        ]:
            raise ValidationError(
                'status must be "passed", "failed", "degraded", '
                '"timedout", or "skipped".'
            )

        link_connected = parsed_yaml.get("link_connected")
        if link_connected is not None:
            if not self.interface:
                raise ValidationError(
                    "link_connected may only be specified if the Script "
                    "accepts an interface parameter."
                )
            if not isinstance(link_connected, bool):
                raise ValidationError("link_connected must be a boolean")

        results = parsed_yaml.get("results")
        if results is None:
            # Results are not defined.
            return parsed_yaml
        elif isinstance(results, dict):
            for key, value in results.items():
                if not isinstance(key, str):
                    raise ValidationError(
                        "All keys in the results dictionary must be strings."
                    )

                if not isinstance(value, list):
                    value = [value]
                for i in value:
                    if type(i) not in [str, float, int, bool]:
                        raise ValidationError(
                            "All values in the results dictionary must be "
                            "a string, float, int, or bool."
                        )
        else:
            raise ValidationError("results must be a dictionary.")

        return parsed_yaml

    def store_result(
        self,
        exit_status=None,
        output=None,
        stdout=None,
        stderr=None,
        result=None,
        script_version_id=None,
        timedout=False,
        runtime=None,
    ):
        # Controllers and Pods are allowed to overwrite their results during any status
        # to prevent new ScriptSets being created everytime a controller
        # starts. This also allows us to avoid creating an RPC call for the
        # rack controller to create a new ScriptSet.
        if self.script_set.node.is_commissioning():
            # Allow PENDING, APPLYING_NETCONF, INSTALLING, and RUNNING scripts
            # incase the node didn't inform MAAS the Script was being run, it
            # just uploaded results.
            assert self.status in SCRIPT_STATUS_RUNNING_OR_PENDING

        if timedout:
            self.status = SCRIPT_STATUS.TIMEDOUT
        elif exit_status is not None:
            self.exit_status = exit_status
            if exit_status == 0:
                self.status = SCRIPT_STATUS.PASSED
            elif self.status == SCRIPT_STATUS.INSTALLING:
                self.status = SCRIPT_STATUS.FAILED_INSTALLING
            elif self.status == SCRIPT_STATUS.APPLYING_NETCONF:
                self.status = SCRIPT_STATUS.FAILED_APPLYING_NETCONF
            else:
                self.status = SCRIPT_STATUS.FAILED

        if output is not None:
            self.output = Bin(output)
        if stdout is not None:
            self.stdout = Bin(stdout)
        if stderr is not None:
            self.stderr = Bin(stderr)
        if result is not None:
            self.result = Bin(result)
            try:
                parsed_yaml = self.read_results()
            except ValidationError as err:
                err_msg = (
                    "%s(%s) sent a script result with invalid YAML: %s"
                    % (
                        self.script_set.node.fqdn,
                        self.script_set.node.system_id,
                        err.message,
                    )
                )
                logger.error(err_msg)
                Event.objects.create_node_event(
                    system_id=self.script_set.node.system_id,
                    event_type=EVENT_TYPES.SCRIPT_RESULT_ERROR,
                    event_description=err_msg,
                )
            else:
                status = parsed_yaml.get("status")
                if status == "passed":
                    self.status = SCRIPT_STATUS.PASSED
                elif status == "failed":
                    self.status = SCRIPT_STATUS.FAILED
                elif status == "degraded":
                    self.status = SCRIPT_STATUS.DEGRADED
                elif status == "timedout":
                    self.status = SCRIPT_STATUS.TIMEDOUT
                elif status == "skipped":
                    self.status = SCRIPT_STATUS.SKIPPED

                link_connected = parsed_yaml.get("link_connected")
                if self.interface and isinstance(link_connected, bool):
                    self.interface.link_connected = link_connected
                    self.interface.save(update_fields=["link_connected"])

        if self.script:
            if script_version_id is not None:
                for script in self.script.script.previous_versions():
                    if script.id == script_version_id:
                        self.script_version = script
                        break
                if self.script_version is None:
                    err_msg = (
                        "%s(%s) sent a script result for %s(%d) with an "
                        "unknown script version(%d)."
                        % (
                            self.script_set.node.fqdn,
                            self.script_set.node.system_id,
                            self.script.name,
                            self.script.id,
                            script_version_id,
                        )
                    )
                    logger.error(err_msg)
                    Event.objects.create_node_event(
                        system_id=self.script_set.node.system_id,
                        event_type=EVENT_TYPES.SCRIPT_RESULT_ERROR,
                        event_description=err_msg,
                    )
            else:
                # If no script version was given assume the latest version
                # was run.
                self.script_version = self.script.script

        # If commissioning result check if its a builtin script, if so run its
        # hook before committing to the database.
        if (
            self.script_set.result_type == RESULT_TYPE.COMMISSIONING
            and self.name in NODE_INFO_SCRIPTS
            and stdout is not None
        ):
            post_process_hook = NODE_INFO_SCRIPTS[self.name]["hook"]
            from metadataserver.api import try_or_log_event

            node = self.script_set.node
            error_message = (
                f"{node.fqdn}({node.system_id}): commissioning script '{self.name}' "
                "failed during post-processing."
            )
            signal_status = try_or_log_event(
                node,
                None,
                error_message,
                post_process_hook,
                node=node,
                output=self.stdout,
                exit_status=self.exit_status,
            )
            # If the script failed to process mark the script as failed to
            # prevent testing from running and help users identify where
            # the error came from. This can happen when a commissioning
            # script generated invalid output.
            if signal_status is not None:
                self.status = SCRIPT_STATUS.FAILED

        if (
            self.status == SCRIPT_STATUS.PASSED
            and self.script
            and self.script.script_type == SCRIPT_TYPE.COMMISSIONING
            and self.script.recommission
        ):
            self.script_set.scriptresult_set.filter(
                script_name__in=NODE_INFO_SCRIPTS
            ).update(
                status=SCRIPT_STATUS.PENDING,
                started=None,
                ended=None,
                updated=now(),
            )

        self.save(runtime=runtime)

    @property
    def history(self):
        qs = ScriptResult.objects.filter(
            script_set__node_id=self.script_set.node_id
        )
        if self.script is not None:
            qs = qs.filter(script=self.script)
        else:
            qs = qs.filter(script_name=self.script_name)
        # XXX ltrager 2017-10-05 - Shows script runs from before MAAS supported
        # the hardware type or physical_blockdevice fields in history.
        # Solves LP: #1721524
        qs = qs.filter(
            Q(physical_blockdevice=self.physical_blockdevice)
            | Q(physical_blockdevice__isnull=True)
        )
        qs = qs.order_by("-id")
        return qs

    def save(self, *args, runtime=None, **kwargs):
        if self.started is None and self.status == SCRIPT_STATUS.RUNNING:
            self.started = datetime.now()
            if "update_fields" in kwargs:
                kwargs["update_fields"].append("started")
        elif self.ended is None and self.status not in (
            SCRIPT_STATUS_RUNNING_OR_PENDING
        ):
            self.ended = datetime.now()
            if "update_fields" in kwargs:
                kwargs["update_fields"].append("ended")
            # LP: #1730799 - If a script is run quickly the POST telling MAAS
            # the script has started comes in after the POST telling MAAS the
            # result.
            if self.started is None:
                if runtime:
                    self.started = self.ended - timedelta(seconds=runtime)
                else:
                    self.started = self.ended
                if "update_fields" in kwargs:
                    kwargs["update_fields"].append("started")

        if self.id is None:
            purge_unlinked_blockdevice = False
            purge_unlinked_interface = False
            for param in self.parameters.values():
                if "value" in param and isinstance(param["value"], dict):
                    if "physical_blockdevice" in param["value"]:
                        self.physical_blockdevice = param["value"].pop(
                            "physical_blockdevice"
                        )
                        purge_unlinked_blockdevice = True
                    elif "interface" in param["value"]:
                        self.interface = param["value"].pop("interface")
                        purge_unlinked_interface = True
            if True in {purge_unlinked_blockdevice, purge_unlinked_interface}:
                # Cleanup previous ScriptResults which failed to map to a
                # required device in a previous run. This may happen due to an
                # issue during commissioning such as not finding devices.
                qs = ScriptResult.objects.filter(
                    script=self.script, script_set__node=self.script_set.node
                )
                # Exclude passed results as they must of been from a previous
                # version of the script which did not require parameters. 2.7
                # adds interface support and the internet-connectivity test
                # has been extended to support interface parameters.
                qs = qs.exclude(status=SCRIPT_STATUS.PASSED)
                if purge_unlinked_blockdevice:
                    qs = qs.filter(physical_blockdevice=None)
                if purge_unlinked_interface:
                    qs = qs.filter(interface=None)
                qs.delete()

        return super().save(*args, **kwargs)

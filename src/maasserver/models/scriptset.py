# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from contextlib import suppress
from datetime import timedelta

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import (
    CASCADE,
    CharField,
    Count,
    DateTimeField,
    F,
    ForeignKey,
    Func,
    IntegerField,
    Manager,
    Model,
    Q,
    TextField,
)
from django.db.models.functions import Coalesce
from django.db.models.query import QuerySet

from maasserver.enum import POWER_STATE, POWER_STATE_CHOICES
from maasserver.exceptions import NoScriptsFound
from maasserver.forms.parameters import ParametersForm
from maasserver.models import Config, Event, Script
from maasserver.models.cleansave import CleanSave
from maasserver.preseed import CURTIN_INSTALL_LOG
from metadataserver import logger
from metadataserver.builtin_scripts.hooks import filter_modaliases
from metadataserver.enum import (
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
    SCRIPT_STATUS_FAILED,
    SCRIPT_STATUS_RUNNING,
    SCRIPT_STATUS_RUNNING_OR_PENDING,
    SCRIPT_TYPE,
)
from provisioningserver.events import EVENT_TYPES


def _get_hw_pairs(script_set):
    """
    Given a ScriptSet return hardware pairs as a list of "key:value" strings.
    """
    hw_pairs_qs = script_set.node.nodemetadata_set.filter(
        Q(key__startswith="system_")
        | Q(key__startswith="mainboard_")
        | Q(key__startswith="firmware_")
        | Q(key__startswith="chassis_")
    ).values_list("key", "value")
    return [":".join(pair) for pair in hw_pairs_qs]


def get_overall_status(script_result_statuses: list[int]) -> int:
    for status in (
        SCRIPT_STATUS.RUNNING,
        SCRIPT_STATUS.APPLYING_NETCONF,
        SCRIPT_STATUS.INSTALLING,
        SCRIPT_STATUS.PENDING,
        SCRIPT_STATUS.ABORTED,
        SCRIPT_STATUS.FAILED,
        SCRIPT_STATUS.FAILED_APPLYING_NETCONF,
        SCRIPT_STATUS.FAILED_INSTALLING,
        SCRIPT_STATUS.TIMEDOUT,
        SCRIPT_STATUS.DEGRADED,
    ):
        for script_result_status in script_result_statuses:
            if script_result_status == status:
                if status in SCRIPT_STATUS_RUNNING:
                    return SCRIPT_STATUS.RUNNING
                elif status in SCRIPT_STATUS_FAILED:
                    return SCRIPT_STATUS.FAILED
                else:
                    return status
    return SCRIPT_STATUS.PASSED


def get_status_from_qs(qs):
    """Given a QuerySet or list of ScriptResults return the set's status."""
    # If no tests have been run the QuerySet or list has no status.
    if isinstance(qs, QuerySet):
        has_status = qs.exists()
    else:
        has_status = len(qs) > 0
    if not has_status:
        return -1
    # The status order below represents the order of precedence.
    # Skipped is omitted here otherwise one skipped test will show
    # a warning icon in the UI on the test tab.
    return get_overall_status(
        [result.status for result in qs if not result.suppressed]
    )


def get_status_from_list_qs(script_result_statuses: list[int]) -> int:
    """Given a list of ScriptResults return the set's status."""
    # If no tests have been run the list has no status.

    if not script_result_statuses:
        return -1

    return get_overall_status(script_result_statuses)


def translate_result_type(result_type):
    if isinstance(result_type, int) or result_type.isdigit():
        ret = int(result_type)
        for result_type_id, _ in RESULT_TYPE_CHOICES:
            if ret == result_type_id:
                return ret
        raise ValidationError("Invalid result type numeric value.")
    elif result_type in ["test", "testing"]:
        return RESULT_TYPE.TESTING
    elif result_type in ["commission", "commissioning"]:
        return RESULT_TYPE.COMMISSIONING
    elif result_type in ["install", "installation"]:
        return RESULT_TYPE.INSTALLATION
    else:
        raise ValidationError(
            "Result type must be commissioning, testing, or installation."
        )


class ScriptSetManager(Manager):
    def create_commissioning_script_set(
        self,
        node,
        scripts=None,
        script_input=None,
        enlisting=False,
    ):
        """Create a new commissioning ScriptSet with ScriptResults

        ScriptResults will be created for all builtin commissioning scripts.
        Optionally a list of user scripts can be given to create ScriptResults
        for. If None all user scripts will be assumed. Scripts may also have
        paramaters passed to them.

        """
        scripts = (
            [] if scripts is None else list(scripts)
        )  # ensure it's always a list
        requested_tags = self._filter_tags(scripts)
        builtin_scripts = Script.objects.filter(default=True)
        builtin_scripts_names = list(
            builtin_scripts.values_list("name", flat=True)
        )
        if node.is_controller:
            # Controllers can only run the builtin scripts for them.
            requested_tags = ["deploy-info"]
            scripts = list(
                builtin_scripts.filter(
                    tags__contains=requested_tags,
                ).values_list("name", flat=True)
            )
        elif enlisting:
            requested_tags = ["enlisting"]
            if Config.objects.get_config("enlist_commissioning"):
                scripts = builtin_scripts_names + requested_tags

            else:
                requested_tags = scripts = ["bmc-config"]
        elif not scripts:
            # No user selected scripts, select all scripts below.
            pass
        elif "none" in scripts:
            # Don't add any scripts besides the ones that come with MAAS.
            scripts = builtin_scripts_names
        else:
            scripts = builtin_scripts_names + scripts

        script_set = self.create(
            node=node,
            result_type=RESULT_TYPE.COMMISSIONING,
            power_state_before_transition=node.power_state,
            tags=requested_tags,
        )

        if not scripts:
            # If the user hasn't selected any commissioning Scripts select
            # all by default excluding for_hardware scripts.
            qs = Script.objects.filter(
                script_type=SCRIPT_TYPE.COMMISSIONING, for_hardware=[]
            ).exclude(tags__contains=["noauto"])
            for script in qs:
                script_set.add_pending_script(script, script_input)
        else:
            self._add_user_selected_scripts(script_set, scripts, script_input)

        self._clean_old(node, RESULT_TYPE.COMMISSIONING, script_set)
        return script_set

    def create_testing_script_set(self, node, scripts=None, script_input=None):
        """Create a new testing ScriptSet with ScriptResults.

        Optionally a list of user scripts and tags can be given to create
        ScriptResults for. If None all Scripts tagged 'commissioning' will be
        assumed. Script may also have parameters passed to them."""
        scripts = [str(i) for i in scripts] if scripts else ["commissioning"]
        script_set = self.create(
            node=node,
            result_type=RESULT_TYPE.TESTING,
            power_state_before_transition=node.power_state,
            tags=self._filter_tags(scripts),
        )

        self._add_user_selected_scripts(script_set, scripts, script_input)

        # A ScriptSet should never be empty. If an empty script set is set as a
        # node's current_testing_script_set the UI will show an empty table and
        # the node-results API will not output any test results.
        if not script_set.scriptresult_set.exists():
            raise NoScriptsFound()

        self._clean_old(node, RESULT_TYPE.TESTING, script_set)
        return script_set

    def create_installation_script_set(self, node):
        """Create a new installation ScriptSet with a ScriptResult."""
        # Avoid circular dependencies.
        from maasserver.models import ScriptResult

        script_set = self.create(
            node=node,
            result_type=RESULT_TYPE.INSTALLATION,
            power_state_before_transition=node.power_state,
        )

        # Curtin uploads the installation log using the full path we specify in
        # the preseed.
        ScriptResult.objects.create(
            script_set=script_set,
            status=SCRIPT_STATUS.PENDING,
            script_name=CURTIN_INSTALL_LOG,
        )

        self._clean_old(node, RESULT_TYPE.INSTALLATION, script_set)
        return script_set

    def create_deployed_machine_script_set(self, machine):
        """Setup ScriptSet for a brown-field deployment.

        Built-in scripts with deploy-info tag are queued up.
        """
        tags = ["deploy-info"]
        script_set = machine.scriptset_set.create(tags=tags)
        scripts = Script.objects.filter(
            script_type=SCRIPT_TYPE.COMMISSIONING,
            default=True,
            tags__contains=tags,
        )
        for script in scripts:
            script_set.add_pending_script(script)
        return script_set

    def _filter_tags(self, names):
        """Return a list of script tags from a list containing names and tags."""
        if not names:
            return []

        all_tags = set(
            Script.objects.annotate(tag=Func(F("tags"), function="unnest"))
            .distinct("tag")
            .values_list("tag", flat=True)
        )
        return list(set(names) & all_tags)

    def _find_scripts(self, script_qs, hw_pairs, modaliases):
        for script in script_qs:
            # If a script is not for specific hardware, it is always included
            if not script.for_hardware:
                yield script
                continue

            # If a script with the for_hardware field is selected by tag only
            # add it if matching hardware is found.
            for hardware in script.for_hardware:
                if hardware in hw_pairs:
                    yield script
                    break
            if filter_modaliases(modaliases, *script.ForHardware):
                yield script

    def _add_user_selected_scripts(
        self, script_set, scripts=None, script_input=None
    ):
        """Add user selected scripts to the ScriptSet."""
        if scripts is None:
            scripts = []
        if script_input is None:
            script_input = {}
        ids = [
            int(id) for id in scripts if isinstance(id, int) or id.isdigit()
        ]
        if script_set.result_type == RESULT_TYPE.COMMISSIONING:
            script_type = SCRIPT_TYPE.COMMISSIONING
        else:
            script_type = SCRIPT_TYPE.TESTING
        qs = Script.objects.filter(
            Q(name__in=scripts) | Q(tags__overlap=scripts) | Q(id__in=ids),
            script_type=script_type,
        )
        hw_pairs = _get_hw_pairs(script_set)
        modaliases = script_set.node.modaliases
        for script in self._find_scripts(qs, hw_pairs, modaliases):
            try:
                script_set.add_pending_script(script, script_input)
            except ValidationError:
                script_set.delete()
                raise

    def _clean_old(self, node, result_type, new_script_set):
        from maasserver.models import ScriptResult

        config_var = {
            RESULT_TYPE.COMMISSIONING: "max_node_commissioning_results",
            RESULT_TYPE.TESTING: "max_node_testing_results",
            RESULT_TYPE.INSTALLATION: "max_node_installation_results",
        }
        limit = Config.objects.get_config(config_var[result_type])

        for script_result in new_script_set.scriptresult_set.all():
            first_to_delete = script_result.history.order_by("-id")[
                limit : limit + 1
            ].first()
            if first_to_delete is not None:
                script_result.history.filter(
                    pk__lte=first_to_delete.pk
                ).delete()

        # LP:1731075 - Before commissioning is run on a node MAAS does not know
        # what storage devices are available on the system. If storage tests
        # are to be run after commissioning MAAS needs to store which
        # storage tests should be run but doesn't know what disks to test.
        # The ParametersForm sets the storage paramater to 'all' as a place
        # holder. When commissioning is finished ScriptSet.regenerate is called
        # which recreates all ScriptResults which accept a storage parameter.
        # If commissioning fails this is never called and the placeholder
        # ScriptResult is left over. This allows the user to see which tests
        # didn't run when commissioning failed but needs to be cleaned up as
        # it is not associated with any disk. Check for this case and clean it
        # up when trying commissioning again.
        for script_result in (
            ScriptResult.objects.filter(
                script_set__result_type=new_script_set.result_type,
                script_set__node=node,
            )
            .exclude(parameters={})
            .exclude(script_set=new_script_set)
        ):
            for param in script_result.parameters.values():
                if (
                    param.get("type") == "storage"
                    and param.get("value") == "all"
                ):
                    script_result.delete()
                    break

        # delete empty ScriptSets
        empty_scriptsets = ScriptSet.objects.annotate(
            results_count=Count("scriptresult")
        ).filter(node=node, result_type=result_type, results_count=0)
        empty_scriptsets.delete()

        # Set previous ScriptSet ScriptResults which are still pending,
        # installing, or running to aborted. The user has requested for the
        # process to be restarted.
        ScriptResult.objects.exclude(script_set=new_script_set).filter(
            script_set__result_type=new_script_set.result_type,
            script_set__node=node,
            status__in=SCRIPT_STATUS_RUNNING_OR_PENDING,
        ).update(status=SCRIPT_STATUS.ABORTED)


class ScriptSet(CleanSave, Model):
    objects = ScriptSetManager()

    last_ping = DateTimeField(blank=True, null=True)

    node = ForeignKey("maasserver.Node", on_delete=CASCADE)

    result_type = IntegerField(
        choices=RESULT_TYPE_CHOICES,
        editable=False,
        default=RESULT_TYPE.COMMISSIONING,
    )

    power_state_before_transition = CharField(
        max_length=10,
        null=False,
        blank=False,
        choices=POWER_STATE_CHOICES,
        default=POWER_STATE.UNKNOWN,
        editable=False,
    )

    tags = ArrayField(TextField(), blank=True, null=True, default=list)

    def __str__(self):
        return f"{self.node.system_id}/{self.result_type_name}"

    def __iter__(self):
        yield from self.scriptresult_set.all()

    @property
    def result_type_name(self):
        return RESULT_TYPE_CHOICES[self.result_type][1]

    @property
    def status(self):
        return get_status_from_qs(
            self.scriptresult_set.all().only(
                "status", "script_set_id", "suppressed"
            )
        )

    @property
    def status_name(self):
        return SCRIPT_STATUS_CHOICES[self.status][1]

    @property
    def started(self):
        try:
            return (
                self.scriptresult_set.all()
                .only("status", "started", "script_set_id")
                .earliest("started")
                .started
            )
        except ObjectDoesNotExist:
            return None

    @property
    def ended(self):
        try:
            # A ScriptSet hasn't finished running until all ScriptResults
            # have finished running.
            if self.scriptresult_set.filter(ended=None).exists():
                return None
            else:
                return (
                    self.scriptresult_set.only(
                        "status", "ended", "script_set_id"
                    )
                    .latest("ended")
                    .ended
                )
        except ObjectDoesNotExist:
            return None

    @property
    def runtime(self):
        if None not in (self.ended, self.started):
            runtime = self.ended - self.started
            return str(runtime - timedelta(microseconds=runtime.microseconds))
        else:
            return ""

    def find_script_result(self, script_result_id=None, script_name=None):
        """Find a script result in the current set."""
        if script_result_id is not None:
            with suppress(ObjectDoesNotExist):
                return self.scriptresult_set.get(id=script_result_id)
        elif script_name:
            return (
                self.scriptresult_set.annotate(
                    scriptname=Coalesce("script_name", "script__name")
                )
                .filter(scriptname=script_name)
                .order_by("-id")
                .first()
            )
        return None

    def add_pending_script(self, script, script_input=None):
        """Create and add a new ScriptResult for the given Script.

        Creates a new ScriptResult for the given script and associates it with
        this ScriptSet. Raises a ValidationError if ParametersForm validation
        fails.
        """
        if script_input is None:
            script_input = {}
        form = ParametersForm(
            data=script_input.get(script.name, {}),
            script=script,
            node=self.node,
        )
        if not form.is_valid():
            raise ValidationError(form.errors)
        for param in form.cleaned_data["input"]:
            self.scriptresult_set.create(
                status=SCRIPT_STATUS.PENDING,
                script=script,
                script_name=script.name,
                parameters=param,
            )

    def select_for_hardware_scripts(self, modaliases=None):
        """Select for_hardware scripts for the given node and user input.

        Goes through an existing ScriptSet and adds any for_hardware tagged
        Script and removes those that were autoselected but the hardware has
        been removed.
        """
        # Only the builtin commissioning scripts run on controllers.
        if self.node.is_controller:
            return

        if modaliases is None:
            modaliases = self.node.modaliases
        hw_pairs = _get_hw_pairs(self)

        # Remove scripts autoselected at the start of commissioning but updated
        # commissioning data shows the Script is no longer applicable.
        script_results = self.scriptresult_set.exclude(script=None)
        script_results = script_results.filter(status=SCRIPT_STATUS.PENDING)
        script_results = script_results.exclude(script__for_hardware=[])
        script_results = script_results.prefetch_related("script")
        script_results = script_results.only(
            "status", "script__for_hardware", "script_set_id"
        )
        for script_result in script_results:
            matches = filter_modaliases(
                modaliases, *script_result.script.ForHardware
            )
            found_hw_match = False
            if hw_pairs:
                for hardware in script_result.script.for_hardware:
                    if hardware in hw_pairs:
                        found_hw_match = True
                        break
            matches = filter_modaliases(
                modaliases, *script_result.script.ForHardware
            )
            if len(matches) == 0 and not found_hw_match:
                script_result.delete()

        # Add Scripts which match the node with current commissioning data.
        scripts = (
            Script.objects.filter(
                script_type=(
                    SCRIPT_TYPE.COMMISSIONING
                    if self.result_type == RESULT_TYPE.COMMISSIONING
                    else SCRIPT_TYPE.TESTING
                ),
                tags__overlap=self.tags,
            )
            .exclude(for_hardware=[])
            .exclude(name__in=[s.name for s in self])
        )
        for script in scripts:
            found_hw_match = False
            if hw_pairs:
                for hardware in script.for_hardware:
                    if hardware in hw_pairs:
                        found_hw_match = True
                        break
            matches = filter_modaliases(modaliases, *script.ForHardware)
            if len(matches) != 0 or found_hw_match:
                try:
                    self.add_pending_script(script)
                except ValidationError as e:
                    err_msg = (
                        "Error adding for_hardware Script %s due to error - %s"
                        % (script.name, str(e))
                    )
                    logger.error(err_msg)
                    Event.objects.create_node_event(
                        system_id=self.node.system_id,
                        event_type=EVENT_TYPES.SCRIPT_RESULT_ERROR,
                        event_description=err_msg,
                    )

    def regenerate(self, storage=True, network=True):
        """Regenerate any ScriptResult which has a storage parameter.

        Deletes and recreates ScriptResults for any ScriptResult which has a
        storage parameter. Used after commissioning has completed when there
        are tests to be run.
        """
        from maasserver.models import ScriptResult

        regenerate_scripts = {}
        for script_result in (
            self.scriptresult_set.filter(status=SCRIPT_STATUS.PENDING)
            .exclude(parameters={})
            .defer("stdout", "stderr", "output", "result")
        ):
            # If there are multiple storage devices or interface on the system
            # for every script which contains a storage or interface type
            # parameter there will be one ScriptResult per device. If we
            # already know a script must be regenearted it can be deleted as
            # the device the ScriptResult is for may no longer exist.
            # Regeneratation below will generate ScriptResults for each
            # existing storage or interface device.
            if script_result.script in regenerate_scripts:
                script_result.delete()
                continue
            # Check if the ScriptResult contains any storage or interface type
            # parameter. If so remove the value of the storage or interface
            # parameter only and add it to the list of Scripts which must be
            # regenearted.
            for param_name, param in script_result.parameters.items():
                if (storage and param["type"] == "storage") or (
                    network and param["type"] == "interface"
                ):
                    # Remove the storage or interface parameter as the storage
                    # device or interface may no longer exist. The
                    # ParametersForm will set the default value(all).
                    script_result.parameters.pop(param_name)
                    # Only preserve the value of the parameter as that is what
                    # the form will validate.
                    regenerate_scripts[script_result.script] = {
                        key: value["value"]
                        for key, value in script_result.parameters.items()
                    }
                    script_result.delete()
                    break

        for script, params in regenerate_scripts.items():
            form = ParametersForm(data=params, script=script, node=self.node)
            if not form.is_valid():
                err_msg = (
                    "Removing Script %s from ScriptSet due to regeneration "
                    "error - %s" % (script.name, dict(form.errors))
                )
                logger.error(err_msg)
                Event.objects.create_node_event(
                    system_id=self.node.system_id,
                    event_type=EVENT_TYPES.SCRIPT_RESULT_ERROR,
                    event_description=err_msg,
                )
                continue
            for i in form.cleaned_data["input"]:
                ScriptResult.objects.create(
                    script_set=self,
                    status=SCRIPT_STATUS.PENDING,
                    script=script,
                    script_name=script.name,
                    parameters=i,
                )

    def delete(self, force=False, *args, **kwargs):
        if not force and self in {
            self.node.current_commissioning_script_set,
            self.node.current_installation_script_set,
        }:
            # Don't allow deleting current_commissioing_script_set as it is
            # the data set MAAS used to gather hardware information about the
            # node. The current_installation_script_set is only set when a node
            # is deployed. Don't allow it to be deleted as it contains info
            # about the OS deployed.
            raise ValidationError(
                "Unable to delete the current %s script set for node: %s"
                % (self.result_type_name.lower(), self.node.fqdn)
            )
        elif self == self.node.current_testing_script_set:
            # MAAS uses the current_testing_script_set to know what testing
            # script set should be shown by default in the UI. If an older
            # version exists set the current_testing_script_set to it.
            try:
                previous_script_set = self.node.scriptset_set.filter(
                    result_type=RESULT_TYPE.TESTING
                )
                previous_script_set = previous_script_set.exclude(id=self.id)
                previous_script_set = previous_script_set.latest("id")
            except ScriptSet.DoesNotExist:
                pass
            else:
                self.node.current_testing_script_set = previous_script_set
                self.node.save(update_fields=["current_testing_script_set"])
        return super().delete(*args, **kwargs)

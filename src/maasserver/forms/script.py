# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Script form."""


from datetime import timedelta
import json
from json import JSONDecodeError
import re
import shlex

from django.core.exceptions import ValidationError
from django.forms import (
    BooleanField,
    CharField,
    DurationField,
    FileField,
    Form,
    ModelForm,
)
import yaml

from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.fields import VersionedTextFileField
from maasserver.forms.parameters import ParametersForm
from maasserver.models import Script
from maasserver.models.script import (
    translate_hardware_type,
    translate_script_parallel,
    translate_script_type,
)
from maasserver.utils.forms import set_form_error
from metadataserver.enum import HARDWARE_TYPE, SCRIPT_PARALLEL, SCRIPT_TYPE
from provisioningserver.events import EVENT_TYPES


class ScriptForm(ModelForm):
    script_type = CharField(
        label="Script type",
        required=False,
        help_text="Script type",
        initial=str(SCRIPT_TYPE.TESTING),
    )

    hardware_type = CharField(
        label="Hardware type",
        required=False,
        help_text="The hardware type the script configures or tests.",
        initial=str(HARDWARE_TYPE.NODE),
    )

    parallel = CharField(
        label="Parallel",
        required=False,
        help_text="Whether the script may run in parallel with other scripts.",
        initial=str(SCRIPT_PARALLEL.DISABLED),
    )

    packages = CharField(
        label="Packages",
        required=False,
        help_text="Packages to be installed with script.",
        initial="",
    )

    timeout = DurationField(
        label="Timeout",
        required=False,
        help_text="Timeout",
        initial=timedelta(0),
    )

    script = VersionedTextFileField(label="Script", help_text="Script content")

    comment = CharField(
        label="Comment",
        required=False,
        help_text="Description of change",
        initial="",
    )

    for_hardware = CharField(
        label="For hardware",
        required=False,
        help_text="Hardware identifiers this script requires to run.",
        initial="",
    )

    apply_configured_networking = BooleanField(required=False)

    class Meta:
        model = Script
        fields = (
            "name",
            "title",
            "description",
            "tags",
            "script_type",
            "hardware_type",
            "parallel",
            "packages",
            "timeout",
            "destructive",
            "script",
            "for_hardware",
            "may_reboot",
            "recommission",
            "apply_configured_networking",
        )

    def __init__(self, instance=None, data=None, edit_default=False, **kwargs):
        self.edit_default = edit_default
        if instance is None:
            script_data_key = "data"
        else:
            script_data_key = "new_data"

        data = data.copy()
        if "comment" in data and "script" in data:
            script_data = {
                "comment": data.get("comment"),
                script_data_key: data.get("script"),
            }
            data["script"] = script_data
            data.pop("comment")
        # Alias type to script_type to allow for consistent naming in the API.
        if "type" in data and "script_type" not in data:
            data["script_type"] = data["type"]
            # self.data is a QueryDict. pop returns a list containing the value
            # while directly accessing it returns just the value.
            data.pop("type")

        super().__init__(instance=instance, data=data, **kwargs)

        if instance is None:
            for field in ["name", "script"]:
                self.fields[field].required = True
        else:
            for field in ["name", "script"]:
                self.fields[field].required = False
            self.fields["script"].initial = instance.script

        # Reading the embedded YAML must happen at the end of initialization
        # so the fields set are validated.
        if "script" in self.data:
            self._read_script()

    def _validate_results(self, results={}):
        valid = True
        if isinstance(results, list):
            for result in results:
                if not isinstance(result, str):
                    set_form_error(
                        self,
                        "results",
                        "Each result in a result list must be a string.",
                    )
                    valid = False
        elif isinstance(results, dict):
            for result in results.values():
                if not isinstance(result, dict):
                    set_form_error(
                        self,
                        "results",
                        "Each result in a result dictionary must be a "
                        "dictionary.",
                    )
                elif "title" not in result:
                    set_form_error(
                        self,
                        "results",
                        "title must be included in a result dictionary.",
                    )
                    valid = False
                else:
                    for key in ["title", "description"]:
                        if key in result and not isinstance(result[key], str):
                            set_form_error(
                                self, "results", "%s must be a string." % key
                            )
                            valid = False
        else:
            set_form_error(
                self,
                "results",
                "results must be a list of strings or a dictionary of "
                "dictionaries.",
            )
            valid = False
        return valid

    def _clean_script(self, parsed_yaml):
        """Clean script data and validate input."""
        # Tags and timeout may not be updated from new embedded YAML. This
        # allows users to receive updated scripts from an upstream maintainer,
        # such as Canonical, while maintaining user defined tags and timeout.

        # Tags must be a comma seperated string for the form.
        tags = parsed_yaml.pop("tags", None)
        if (
            tags is not None
            and self.instance.id is None
            and "tags" not in self.data
        ):
            tags_valid = True
            if isinstance(tags, str):
                self.data["tags"] = tags
            elif isinstance(tags, list):
                for tag in tags:
                    if not isinstance(tag, str):
                        tags_valid = False
                        continue
                if tags_valid:
                    self.data["tags"] = ",".join(tags)
            else:
                tags_valid = False
            if not tags_valid:
                set_form_error(
                    self,
                    "tags",
                    "Embedded tags must be a string of comma seperated "
                    "values, or a list of strings.",
                )

        # Timeout must be a string for the form.
        timeout = parsed_yaml.pop("timeout", None)
        if (
            timeout is not None
            and self.instance.id is None
            and "timeout" not in self.data
        ):
            self.data["timeout"] = str(timeout)

        # Packages and for_hardware must be a JSON string for the form.
        for key in ["packages", "for_hardware"]:
            value = parsed_yaml.pop(key, None)
            if value is not None and key not in self.data:
                self.data[key] = json.dumps(value)

        for key, value in parsed_yaml.items():
            if key in self.fields:
                error = False
                if key not in self.data:
                    self.data[key] = value
                elif key == "script_type":
                    # The deprecated Commissioning API always sets the
                    # script_type to commissioning as it has always only
                    # accepted commissioning scripts while the form sets
                    # the default type to testing. If the YAML matches the
                    # type allow it.
                    try:
                        if translate_script_type(
                            value
                        ) != translate_script_type(self.data[key]):
                            error = True
                    except ValidationError:
                        error = True
                elif value != self.data[key]:
                    # Only allow form data for fields defined in the YAML if
                    # the data matches.
                    error = True

                if error:
                    set_form_error(
                        self,
                        key,
                        "May not override values defined in embedded YAML.",
                    )

    def _read_script(self):
        """Read embedded YAML configuration in a script.

        Search for supported MAAS script metadata in the script and
        read the values. Leading '#' are ignored. If the values are
        fields they will be entered in the form.
        """
        yaml_delim = re.compile(
            r"\s*#\s*-+\s*(Start|End) MAAS (?P<version>\d+\.\d+) "
            r"script metadata\s+-+",
            re.I,
        )
        found_version = None
        yaml_content = ""

        if isinstance(self.data["script"], dict):
            if "new_data" in self.data["script"]:
                script = self.data["script"]["new_data"]
            else:
                script = self.data["script"]["data"]
        else:
            script = self.data["script"]

        script_splitlines = script.splitlines()
        if len(script_splitlines) >= 1 and not script_splitlines[0].startswith(
            "#!/"
        ):
            set_form_error(self, "script", "Must start with shebang.")

        for line in script_splitlines[1:]:
            m = yaml_delim.search(line)
            if m is not None:
                if found_version is None and m.group("version") == "1.0":
                    # Found the start of the embedded YAML
                    found_version = m.group("version")
                    continue
                elif found_version == m.group("version"):
                    # Found the end of the embedded YAML
                    break
            elif found_version is not None and line.strip() != "":
                # Capture all lines inbetween the deliminator
                if "#" not in line:
                    set_form_error(self, "script", 'Missing "#" on YAML line.')
                    return
                yaml_content += "%s\n" % line.split("#", 1)[1]

        try:
            parsed_yaml = yaml.safe_load(yaml_content)
        except yaml.YAMLError as err:
            set_form_error(self, "script", "Invalid YAML: %s" % err)
            return

        if not isinstance(parsed_yaml, dict):
            return

        self.instance.results = parsed_yaml.pop("results", {})
        self.instance.parameters = parsed_yaml.pop("parameters", {})

        self._clean_script(parsed_yaml)

    def clean_packages(self):
        if self.cleaned_data["packages"] == "":
            return self.instance.packages
        else:
            packages = json.loads(self.cleaned_data["packages"])

            # Automatically convert into a list incase only one package is
            # needed.
            for key in ["apt", "snap", "url"]:
                if key in packages and not isinstance(packages[key], list):
                    packages[key] = [packages[key]]

            for key in ["apt", "url"]:
                if key in packages:
                    for package in packages[key]:
                        if not isinstance(package, str):
                            set_form_error(
                                self,
                                "packages",
                                "Each %s package must be a string." % key,
                            )
            if "snap" in packages:
                for package in packages["snap"]:
                    if isinstance(package, dict):
                        if "name" not in package or not isinstance(
                            package["name"], str
                        ):
                            set_form_error(
                                self,
                                "packages",
                                "Snap package name must be defined.",
                            )
                        if "channel" in package and package["channel"] not in [
                            "stable",
                            "edge",
                            "beta",
                            "candidate",
                        ]:
                            set_form_error(
                                self,
                                "packages",
                                "Snap channel must be stable, edge, beta, "
                                "or candidate.",
                            )
                        if "mode" in package and package["mode"] not in [
                            "classic",
                            "dev",
                            "jail",
                        ]:
                            set_form_error(
                                self,
                                "packages",
                                "Snap mode must be classic, dev, or jail.",
                            )
                    elif not isinstance(package, str):
                        set_form_error(
                            self, "packages", "Snap package must be a string."
                        )
            return packages

    def clean_for_hardware(self):
        """Convert from JSON and validate for_hardware input."""
        if self.cleaned_data["for_hardware"] == "":
            return self.instance.for_hardware
        try:
            for_hardware = json.loads(self.cleaned_data["for_hardware"])
        except JSONDecodeError:
            for_hardware = self.cleaned_data["for_hardware"]
        if isinstance(for_hardware, str):
            for_hardware = for_hardware.split(",")
        if not isinstance(for_hardware, list):
            set_form_error(self, "for_hardware", "Must be a list or string")
            return
        regex = re.compile(
            r"^modalias:.+|pci:[\da-f]{4}:[\da-f]{4}|"
            r"usb:[\da-f]{4}:[\da-f]{4}|"
            r"system_vendor:.*|"
            r"system_product:.*|"
            r"system_version:.*|"
            r"mainboard_vendor:.*|"
            r"mainboard_product:.*$",
            re.I,
        )
        for hw_id in for_hardware:
            if regex.search(hw_id) is None:
                set_form_error(
                    self,
                    "for_hardware",
                    "Hardware identifier '%s' must be a modalias, PCI ID, "
                    "USB ID, system vendor, system product, system version, "
                    "mainboard vendor, or mainboard product." % hw_id,
                )
        return for_hardware

    def clean(self):
        cleaned_data = super().clean()
        # If a field wasn't passed in keep the old values when updating.
        if self.instance.id is not None:
            for field in self._meta.fields:
                if field not in self.data:
                    cleaned_data[field] = getattr(self.instance, field)

        script_type = cleaned_data["script_type"]
        if script_type == "":
            cleaned_data["script_type"] = self.instance.script_type
        else:
            try:
                cleaned_data["script_type"] = translate_script_type(
                    script_type
                )
            except ValidationError as e:
                set_form_error(self, "script_type", e)

        hardware_type = cleaned_data["hardware_type"]
        if hardware_type == "":
            cleaned_data["hardware_type"] = self.instance.hardware_type
        else:
            try:
                cleaned_data["hardware_type"] = translate_hardware_type(
                    hardware_type
                )
            except ValidationError as e:
                set_form_error(self, "hardware_type", e)

        parallel = cleaned_data["parallel"]
        if parallel == "":
            cleaned_data["parallel"] = self.instance.parallel
        else:
            try:
                cleaned_data["parallel"] = translate_script_parallel(parallel)
            except ValidationError as e:
                set_form_error(self, "parallel", e)

        return cleaned_data

    def is_valid(self):
        valid = super().is_valid()

        if valid and self.instance.default and not self.edit_default:
            for field in self.Meta.fields:
                if field in ["tags", "timeout"]:
                    continue
                if field in self.data:
                    set_form_error(
                        self,
                        field,
                        "Not allowed to change on default scripts.",
                    )
                    valid = False

        name = self.data.get("name")
        # none is used to tell the API to not run testing_scripts during
        # commissioning.
        if name is not None and name.lower() == "none":
            set_form_error(self, "name", '"none" is a reserved name.')
            valid = False

        # The name can't be a digit as MAAS allows scripts to be selected by
        # id.
        if name is not None and name.isdigit():
            set_form_error(self, "name", "Cannot be a number.")
            valid = False

        if name is not None and shlex.quote(name) != name:
            set_form_error(
                self,
                "name",
                "Name '%s' contains disallowed characters, e.g. space or quotes."
                % name,
            )
            valid = False

        # If comment and script exist __init__ combines both fields into a dict
        # to pass to VersionedTextFileField.
        if "comment" in self.data:
            set_form_error(
                self,
                "comment",
                '"comment" may only be used when specifying a "script" '
                "as well.",
            )
            valid = False

        if "script" in self.data:
            if not self._validate_results(self.instance.results):
                valid = False

        if "parameters" in self.data:
            params_form = ParametersForm(data=self.data.get("parameters"))
            if not params_form.is_valid():
                valid = False

        if (
            not valid
            and self.instance.script_id is not None
            and self.initial.get("script") != self.instance.script_id
            and self.instance.script.id is not None
        ):
            # If form validation failed cleanup any new VersionedTextFile
            # created by the VersionedTextFileField.
            self.instance.script.delete()
        return valid

    def save(self, *args, **kwargs):
        request = kwargs.pop("request", None)
        endpoint = kwargs.pop("endpoint", None)
        script = super().save(*args, **kwargs)

        # Create audit event log if endpoint and request supplied.
        if request is not None and endpoint is not None:
            create_audit_event(
                EVENT_TYPES.SETTINGS,
                endpoint,
                request,
                None,
                description="Saved script '%s'." % script.name,
            )
        return script


class CommissioningScriptForm(Form):
    """CommissioningScriptForm for the UI

    The CommissioningScriptForm accepts a commissioning script from the
    settings page in the UI. This form handles accepting the file upload
    and setting the script_type to commissioning if no script_script is
    set in the embedded YAML. The ScriptForm above validates the script
    itself.
    """

    content = FileField(label="Commissioning script", allow_empty_file=False)

    def __init__(self, instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._form = None

    def clean_content(self):
        content = self.cleaned_data["content"]
        script_name = content.name
        script_content = content.read().decode()
        try:
            script = Script.objects.get(name=script_name)
        except Script.DoesNotExist:
            form = ScriptForm(data={"script": script_content})
            # If the form isn't valid due to the name it may be because the
            # embedded YAML doesn't define a name. Try again defining it.
            if not form.is_valid() and "name" in form.errors:
                form = ScriptForm(
                    data={"name": script_name, "script": script_content}
                )
        else:
            form = ScriptForm(data={"script": script_content}, instance=script)

        self._form = form
        return content

    def is_valid(self):
        valid = super().is_valid()

        # If content is empty self.clean_content isn't run.
        if self._form is not None and not self._form.is_valid():
            # This form only has content so all errors must be on that field.
            if "content" not in self.errors:
                self.errors["content"] = []
            for key, errors in self._form.errors.items():
                for error in errors:
                    self.errors["content"].append(f"{key}: {error}")
            return False
        else:
            return valid

    def save(self, request, *args, **kwargs):
        script = self._form.save(
            *args,
            **kwargs,
            commit=False,
            request=request,
            endpoint=ENDPOINT.UI,
        )
        # If the embedded script data did not set a script type,
        # set it to commissioning.
        if "script_type" not in self._form.data:
            script.script_type = SCRIPT_TYPE.COMMISSIONING
        script.save()


class TestingScriptForm(Form):
    """TestingScriptForm for the UI

    The TestingScriptForm accepts a test script from the
    settings page in the UI. This form handles accepting the file upload
    and setting the script_type to test if no script_script is
    set in the embedded YAML. The ScriptForm above validates the script
    itself.
    """

    content = FileField(label="Test script", allow_empty_file=False)

    def __init__(self, instance=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._form = None

    def clean_content(self):
        content = self.cleaned_data["content"]
        script_name = content.name
        script_content = content.read().decode()
        try:
            script = Script.objects.get(name=script_name)
        except Script.DoesNotExist:
            form = ScriptForm(data={"script": script_content})
            # If the form isn't valid due to the name it may be because the
            # embedded YAML doesn't define a name. Try again defining it.
            if not form.is_valid() and "name" in form.errors:
                form = ScriptForm(
                    data={"name": script_name, "script": script_content}
                )
        else:
            form = ScriptForm(data={"script": script_content}, instance=script)

        self._form = form
        return content

    def is_valid(self):
        valid = super().is_valid()

        # If content is empty self.clean_content isn't run.
        if self._form is not None and not self._form.is_valid():
            # This form only has content so all errors must be on that field.
            if "content" not in self.errors:
                self.errors["content"] = []
            for key, errors in self._form.errors.items():
                for error in errors:
                    self.errors["content"].append(f"{key}: {error}")
            return False
        else:
            return valid

    def save(self, request, *args, **kwargs):
        script = self._form.save(
            *args,
            **kwargs,
            commit=False,
            request=request,
            endpoint=ENDPOINT.UI,
        )
        # If the embedded script data did not set a script type,
        # set it to testing.
        if "script_type" not in self._form.data:
            script.script_type = SCRIPT_TYPE.TESTING
        script.save()

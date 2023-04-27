# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Script`."""


from base64 import b64encode
from email.utils import format_datetime

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from formencode.validators import Bool, Int, String
from piston3.utils import rc

from maasserver.api.support import admin_method, operation, OperationsHandler
from maasserver.api.utils import get_mandatory_param, get_optional_param
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms.script import ScriptForm
from maasserver.models import Script
from maasserver.models.script import (
    translate_hardware_type,
    translate_script_type,
)
from provisioningserver.events import EVENT_TYPES


class NodeScriptsHandler(OperationsHandler):
    """
    Manage custom scripts.

    This functionality is only available to administrators.
    """

    api_doc_section_name = "Node Scripts"

    update = delete = None

    @classmethod
    def resource_uri(cls):
        return ("scripts_handler", [])

    @admin_method
    def create(self, request):
        """@description-title Create a new script
        @description Create a new script.

        @param (string) "name" [required=true] The name of the script.

        @param (string) "title" [required=false] The title of the script.

        @param (string) "description" [required=false] A description of what
        the script does.

        @param (string) "tags" [required=false] A comma seperated list of tags
        for this script.

        @param (string) "type" [required=false] The script_type defines when
        the script should be used: ``testing`` or ``commissioning``. Defaults
        to ``testing``.

        @param (string) "hardware_type" [required=false] The hardware_type
        defines what type of hardware the script is assoicated with. May be
        CPU, memory, storage, network, or node.

        @param (int) "parallel" [required=false] Whether the script may be
        run in parallel with other scripts. May be disabled to run by itself,
        instance to run along scripts with the same name, or any to run along
        any script. 1 == True, 0 == False.

        @param (int) "timeout" [required=false] How long the script is allowed
        to run before failing.  0 gives unlimited time, defaults to 0.

        @param (boolean) "destructive" [required=false] Whether or not the
        script overwrites data on any drive on the running system. Destructive
        scripts can not be run on deployed systems. Defaults to false.

        @param (string) "script" [required=false] The content of the script to
        be uploaded in binary form. Note: this is not a normal parameter, but
        a file upload. Its filename is ignored; MAAS will know it by the name
        you pass to the request. Optionally you can ignore the name and script
        parameter in favor of uploading a single file as part of the request.

        @param (string) "comment" [required=false] A comment about what this
        change does.

        @param (string) "for_hardware" [required=false] A list of modalias, PCI
        IDs, and/or USB IDs the script will automatically run on. Must start
        with ``modalias:``, ``pci:``, or ``usb:``.

        @param (boolean) "may_reboot" [required=false] Whether or not the
        script may reboot the system while running.

        @param (string) "recommission" [required=false] Whether builtin
        commissioning scripts should be rerun after successfully running this
        scripts.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the new script.
        @success-example "success-json" [exkey=scripts-create] placeholder text
        """
        data = request.data.copy()
        if "script" in request.FILES:
            data["script"] = request.FILES.get("script").read()
        elif len(request.FILES) == 1:
            for name, script in request.FILES.items():
                data["name"] = name
                data["script"] = script.read()
        form = ScriptForm(data=data)
        if form.is_valid():
            return form.save(request=request, endpoint=ENDPOINT.API)
        else:
            raise MAASAPIValidationError(form.errors)

    def read(self, request):
        """@description-title List stored scripts
        @description Return a list of stored scripts.

        Note that parameters should be passed in the URI. E.g.
        ``/script/?type=testing``.

        @param (string) "type" [required=false] Only return scripts with the
        given type. This can be ``testing`` or ``commissioning``. Defaults to
        showing both.

        @param (string) "hardware_type" [required=false] Only return scripts
        for the given hardware type.  Can be ``cpu``, ``memory``, ``storage``,
        ``network``, or ``node``.  Defaults to all.

        @param (string) "include_script" [required=false] Include the base64-
        encoded script content.

        @param (string) "filters" [required=false] A comma seperated list to
        show only results with a script name or tag.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        script objects.
        @success-example "success-json" [exkey=scripts-read] placeholder text
        """
        qs = Script.objects.all()

        script_type = get_optional_param(request.GET, "type")
        if script_type is not None:
            try:
                script_type = translate_script_type(script_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)
            else:
                qs = qs.filter(script_type=script_type)

        hardware_type = get_optional_param(request.GET, "hardware_type")
        if hardware_type is not None:
            try:
                hardware_type = translate_hardware_type(hardware_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)
            else:
                qs = qs.filter(hardware_type=hardware_type)

        include_script = get_optional_param(
            request.GET, "include_script", False, Bool
        )
        filters = get_optional_param(request.GET, "filters", None, String)
        if filters is not None:
            filters = set(filters.split(","))

        ret = []
        for script in qs:
            if (
                filters is not None
                and script.name not in filters
                and filters.isdisjoint(script.tags)
            ):
                continue
            else:
                script.include_script = include_script
                ret.append(script)

        return ret


class NodeScriptHandler(OperationsHandler):
    """Manage or view a custom script."""

    api_doc_section_name = "Node Script"

    fields = (
        "id",
        "name",
        "title",
        "description",
        "tags",
        "type",
        "type_name",
        "hardware_type",
        "hardware_type_name",
        "parallel",
        "parallel_name",
        "results",
        "parameters",
        "packages",
        "timeout",
        "destructive",
        "for_hardware",
        "may_reboot",
        "recommission",
        "history",
        "default",
        "apply_configured_networking",
    )
    model = Script

    create = None

    @classmethod
    def resource_uri(cls, script=None):
        # See the comment in NodeHandler.resource_uri
        script_name = "name"
        if script is not None:
            script_name = script.name
        return ("script_handler", (script_name,))

    @classmethod
    def type(handler, script):
        return script.script_type

    @classmethod
    def type_name(handler, script):
        return script.script_type_name

    @classmethod
    def history(handler, script):
        results = []
        for script_ver in script.script.previous_versions():
            version = {
                "id": script_ver.id,
                "comment": script_ver.comment,
                "created": format_datetime(script_ver.created),
            }
            if getattr(script, "include_script", False):
                version["data"] = b64encode(script_ver.data.encode())
            results.append(version)
        return results

    def read(self, request, name):
        """@description-title Return script metadata
        @description Return metadata belonging to the script with the given
        name.

        @param (string) "{name}" [required=true] The script's name.

        @param (string) "include_script" [required=false] Include the base64
        encoded script content if any value is given for include_script.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the script.
        @success-example "success-json" [exkey=scripts-read-by-name]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested script is not found.
        @error-example "not-found"
            No Script matches the given query.
        """
        if name.isdigit():
            script = get_object_or_404(Script, id=int(name))
        else:
            script = get_object_or_404(Script, name=name)
        script.include_script = get_optional_param(
            request.GET, "include_script", False, Bool
        )
        return script

    @admin_method
    def delete(self, request, name):
        """@description-title Delete a script
        @description Deletes a script with the given name.

        @param (string) "{name}" [required=true] The script's name.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested script is not found.
        @error-example "not-found"
            No Script matches the given query.
        """
        if name.isdigit():
            script = get_object_or_404(Script, id=int(name))
        else:
            script = get_object_or_404(Script, name=name)

        if script.default:
            raise MAASAPIValidationError("Unable to delete default script")

        script.delete()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            ENDPOINT.API,
            request,
            None,
            description="Deleted script '%s'." % script.name,
        )
        return rc.DELETED

    @admin_method
    def update(self, request, name):
        """@description-title Update a script
        @description Update a script with the given name.

        @param (string) "{name}" [required=true] The name of the script.

        @param (string) "title" [required=false] The title of the script.

        @param (string) "description" [required=false] A description of what
        the script does.

        @param (string) "tags" [required=false] A comma seperated list of tags
        for this script.

        @param (string) "type" [required=false] The type defines when the
        script should be used. Can be ``testing`` or ``commissioning``,
        defaults to ``testing``.

        @param (string) "hardware_type" [required=false] The hardware_type
        defines what type of hardware the script is assoicated with. May be
        ``cpu``, ``memory``, ``storage``, ``network``, or ``node``.

        @param (int) "parallel" [required=false] Whether the script may be
        run in parallel with other scripts. May be disabled to run by itself,
        instance to run along scripts with the same name, or any to run along
        any script. ``1`` == True, ``0`` == False.

        @param (int) "timeout" [required=false] How long the script is allowed
        to run before failing.  0 gives unlimited time, defaults to 0.

        @param (boolean) "destructive" [required=false] Whether or not the
        script overwrites data on any drive on the running system. Destructive
        scripts can not be run on deployed systems. Defaults to false.

        @param (string) "script" [required=false] The content of the script to
        be uploaded in binary form. Note: this is not a normal parameter, but
        a file upload. Its filename is ignored; MAAS will know it by the name
        you pass to the request. Optionally you can ignore the name and script
        parameter in favor of uploading a single file as part of the request.

        @param (string) "comment" [required=false] A comment about what this
        change does.

        @param (string) "for_hardware" [required=false] A list of modalias, PCI
        IDs, and/or USB IDs the script will automatically run on. Must start
        with ``modalias:``, ``pci:``, or ``usb:``.

        @param (boolean) "may_reboot" [required=false] Whether or not the
        script may reboot the system while running.

        @param (boolean) "recommission" [required=false] Whether built-in
        commissioning scripts should be rerun after successfully running this
        scripts.

        @param (boolean) "apply_configured_networking" [required=false] Whether
        to apply the provided network configuration before the script runs.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the updated script.
        @success-example "success-json" [exkey=scripts-update] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested script is not found.
        @error-example "not-found"
            No Script matches the given query.
        """
        if name.isdigit():
            script = get_object_or_404(Script, id=int(name))
        else:
            script = get_object_or_404(Script, name=name)

        data = request.data.copy()
        if "script" in request.FILES:
            data["script"] = request.FILES.get("script").read()
        elif len(request.FILES) == 1:
            for name, script_content in request.FILES.items():
                data["name"] = name
                data["script"] = script_content.read()

        form = ScriptForm(instance=script, data=data)
        if form.is_valid():
            return form.save(request=request, endpoint=ENDPOINT.API)
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=True)
    def download(self, request, name):
        """@description-title Download a script
        @description Download a script with the given name.

        @param (string) "{name}" [required=true] The name of the script.

        @param (int) "revision" [required=false] What revision to download,
        latest by default. Can use rev as a shortcut.

        @success (http-status-code) "server-success" 200
        @success (content) "success-text" A plain-text representation of the
        requested script.
        @success-example "success-text" [exkey=scripts-download] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested script is not found.
        @error-example "not-found"
            No Script matches the given query.
        """
        if name.isdigit():
            script = get_object_or_404(Script, id=int(name))
        else:
            script = get_object_or_404(Script, name=name)
        revision = get_optional_param(request.GET, "revision", None, Int)
        if revision is None:
            revision = get_optional_param(request.GET, "rev", None, Int)
        if revision is not None:
            for rev in script.script.previous_versions():
                if rev.id == revision:
                    return HttpResponse(
                        rev.data, content_type="application/binary"
                    )
            raise MAASAPIValidationError("%s not found in history" % revision)
        else:
            return HttpResponse(
                script.script.data, content_type="application/binary"
            )

    @admin_method
    @operation(idempotent=False)
    def revert(self, request, name):
        """@description-title Revert a script version
        @description Revert a script with the given name to an earlier version.

        @param (string) "{name}" [required=true] The name of the script.

        @param (int) "to" [required=false] What revision in the script's
        history to revert to. This can either be an ID or a negative number
        representing how far back to go.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the reverted script.
        @success-example "success-json" [exkey=scripts-revert] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested script is not found.
        @error-example "not-found"
            No Script matches the given query.
        """
        revert_to = get_mandatory_param(request.data, "to", Int)

        if name.isdigit():
            script = get_object_or_404(Script, id=int(name))
        else:
            script = get_object_or_404(Script, name=name)
        try:
            if script.default:
                raise MAASAPIValidationError("Unable to revert default script")

            def gc_hook(value):
                script.script = value
                script.save()

            script.script.revert(revert_to, gc_hook=gc_hook)
            create_audit_event(
                EVENT_TYPES.SETTINGS,
                ENDPOINT.API,
                request,
                None,
                description=(
                    "Reverted script '%s' to revision '%s'."
                    % (script.name, revert_to)
                ),
            )
            return script
        except ValueError as e:
            raise MAASAPIValidationError(e.args[0])

    @admin_method
    @operation(idempotent=False)
    def add_tag(self, request, name):
        """@description-title Add a tag
        @description Add a single tag to a script with the given name.

        @param (string) "{name}" [required=true] The name of the script.

        @param (string) "tag" [required=false] The tag being added.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the updated script.
        @success-example "success-json" [exkey=scripts-add-tag] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested script is not found.
        @error-example "not-found"
            No Script matches the given query.
        """
        tag = get_mandatory_param(request.data, "tag", String)

        if "," in tag:
            raise MAASAPIValidationError('Tag may not contain a ",".')

        if name.isdigit():
            script = get_object_or_404(Script, id=int(name))
        else:
            script = get_object_or_404(Script, name=name)

        script.add_tag(tag)
        script.save()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            ENDPOINT.API,
            request,
            None,
            description=(f"Added tag '{tag}' to script '{script.name}'."),
        )
        return script

    @admin_method
    @operation(idempotent=False)
    def remove_tag(self, request, name):
        """@description-title Remove a tag
        @description Remove a tag from a script with the given name.

        @param (string) "{name}" [required=true] The name of the script.

        @param (string) "tag" [required=false] The tag being removed.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the updated script.
        @success-example "success-json" [exkey=scripts-remove-tag] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested script is not found.
        @error-example "not-found"
            No Script matches the given query.
        """
        tag = get_mandatory_param(request.data, "tag", String)

        if name.isdigit():
            script = get_object_or_404(Script, id=int(name))
        else:
            script = get_object_or_404(Script, name=name)

        script.remove_tag(tag)
        script.save()
        create_audit_event(
            EVENT_TYPES.SETTINGS,
            ENDPOINT.API,
            request,
            None,
            description=(f"Removed tag '{tag}' from script '{script.name}'."),
        )
        return script

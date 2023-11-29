# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `ScriptResults`."""


from base64 import b64encode
from collections import OrderedDict
from email.utils import format_datetime
from io import BytesIO
import os
import re
import tarfile
import time

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from formencode.validators import Bool, String, StringBool
from piston3.utils import rc

from maasserver.api.support import admin_method, operation, OperationsHandler
from maasserver.api.utils import get_optional_param
from maasserver.exceptions import MAASAPIValidationError
from maasserver.models import Node, ScriptSet
from maasserver.models.script import translate_hardware_type
from maasserver.models.scriptset import translate_result_type
from maasserver.permissions import NodePermission


def fmt_time(dt):
    """Return None if None otherwise returned formatted datetime."""
    if dt is None:
        return None
    else:
        return format_datetime(dt)


def filter_script_results(script_set, filters, hardware_type=None):
    if filters is None:
        script_results = list(script_set)
    else:
        script_results = []
        # ScriptResults don't always have a Script associated with them.
        # e.g commissioning scripts.
        for script_result in script_set:
            if script_result.script is None:
                tags = []
            else:
                tags = script_result.script.tags
            for f in filters:
                if (
                    f == script_result.name
                    or f in tags
                    or (f.isdigit() and int(f) == script_result.id)
                ):
                    script_results.append(script_result)
    if hardware_type is not None:
        script_results = [
            script_result
            for script_result in script_results
            if script_result.script is not None
            and script_result.script.hardware_type == hardware_type
        ]
    return sorted(
        script_results,
        key=lambda script_result: (
            script_result.name,
            getattr(script_result.physical_blockdevice, "name", None),
            getattr(script_result.interface, "name", None),
        ),
    )


class NodeScriptResultsHandler(OperationsHandler):
    """Manage node script results."""

    api_doc_section_name = "Node Script Result"

    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ("script_results_handler", ["system_id"])

    def read(self, request, system_id):
        """@description-title Return script results
        @description Return a list of script results grouped by run for the
        given system_id.

        @param (string) "{system_id}" [required=true] The machine's system_id.

        @param (string) "type" [required=false] Only return scripts with the
        given type. This can be ``commissioning``, ``testing``, ``installion``
        or ``release``. Defaults to showing all.

        @param (string) "hardware_type" [required=false] Only return scripts
        for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or
        ``storage``.  Defaults to all.

        @param (string) "include_output" [required=false] Include base64
        encoded output from the script. Note that any value of include_output
        will include the encoded output from the script.

        @param (string) "filters" [required=false] A comma seperated list to
        show only results with a script name or tag.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of
        script result objects.
        @success-example "success-json" [exkey=script-results-read]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        result_type = get_optional_param(request.GET, "type")
        include_output = get_optional_param(
            request.GET, "include_output", False, Bool
        )
        filters = get_optional_param(request.GET, "filters", None, String)
        if filters is not None:
            filters = filters.split(",")
        if result_type is not None:
            try:
                result_type = translate_result_type(result_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)
            else:
                qs = ScriptSet.objects.filter(
                    node=node, result_type=result_type
                )
        else:
            qs = ScriptSet.objects.filter(node=node)

        hardware_type = get_optional_param(request.GET, "hardware_type")
        if hardware_type is not None:
            try:
                hardware_type = translate_hardware_type(hardware_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)

        ret = []
        for script_set in qs:
            script_set.include_output = include_output
            script_set.filters = filters
            script_set.hardware_type = hardware_type
            ret.append(script_set)
        return ret


class NodeScriptResultHandler(OperationsHandler):
    """Manage node script results."""

    api_doc_section_name = "Node Script Result"

    fields = (
        "id",
        "system_id",
        "type",
        "type_name",
        "last_ping",
        "status",
        "status_name",
        "started",
        "ended",
        "runtime",
        "results",
        "suppressed",
    )

    model = ScriptSet

    create = None

    @classmethod
    def resource_uri(cls, script_set=None):
        # See the comment in NodeHandler.resource_uri.
        if script_set is None:
            system_id = "system_id"
            script_set_id = "id"
        else:
            system_id = script_set.node.system_id
            script_set_id = script_set.id
        return ("script_result_handler", [system_id, script_set_id])

    @classmethod
    def system_id(cls, script_set):
        return script_set.node.system_id

    @classmethod
    def type(cls, script_set):
        return script_set.result_type

    @classmethod
    def type_name(cls, script_set):
        return script_set.result_type_name

    @classmethod
    def last_ping(cls, script_set):
        return fmt_time(script_set.last_ping)

    @classmethod
    def started(cls, script_set):
        return fmt_time(script_set.started)

    @classmethod
    def ended(cls, script_set):
        return fmt_time(script_set.ended)

    @classmethod
    def results(cls, script_set):
        results = []
        for script_result in filter_script_results(
            script_set, script_set.filters, script_set.hardware_type
        ):
            # Don't show password parameter values over the API.
            for parameter in script_result.parameters.values():
                if (
                    parameter.get("type") == "password"
                    and "value" in parameter
                ):
                    parameter["value"] = "REDACTED"
            result = {
                "id": script_result.id,
                "created": format_datetime(script_result.created),
                "updated": format_datetime(script_result.updated),
                "name": script_result.name,
                "status": script_result.status,
                "status_name": script_result.status_name,
                "exit_status": script_result.exit_status,
                "started": fmt_time(script_result.started),
                "ended": fmt_time(script_result.ended),
                "runtime": script_result.runtime,
                "starttime": script_result.starttime,
                "endtime": script_result.endtime,
                "estimated_runtime": script_result.estimated_runtime,
                "parameters": script_result.parameters,
                "script_id": script_result.script_id,
                "script_revision_id": script_result.script_version_id,
                "suppressed": script_result.suppressed,
            }
            if script_set.include_output:
                result["output"] = b64encode(script_result.output)
                result["stdout"] = b64encode(script_result.stdout)
                result["stderr"] = b64encode(script_result.stderr)
                result["result"] = b64encode(script_result.result)
            results.append(result)
        return results

    def _get_script_set(self, request, system_id, id):
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        script_sets = {
            "current-commissioning": node.current_commissioning_script_set,
            "current-testing": node.current_testing_script_set,
            "current-installation": node.current_installation_script_set,
        }
        script_set = script_sets.get(id)
        if script_set is None and not id.isdigit():
            raise MAASAPIValidationError(
                'Unknown id "%s" must be current-commissioning, '
                "current-testing, current-installation, or the id number of a "
                "specific result." % id
            )
        elif script_set is None:
            return get_object_or_404(ScriptSet, id=id, node=node)
        else:
            return script_set

    def read(self, request, system_id, id):
        """@description-title Get specific script result
        @description View a set of test results for a given system_id and
        script id.

        "id" can either by the script set id, ``current-commissioning``,
        ``current-testing``, or ``current-installation``.

        @param (string) "{system_id}" [required=true] The machine's system_id.
        @param (string) "{id}" [required=true] The script result id.

        @param (string) "hardware_type" [required=false] Only return scripts
        for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or
        ``storage``.  Defaults to all.

        @param (string) "include_output" [required=false] Include the base64
        encoded output from the script if any value for include_output is
        given.

        @param (string) "filters" [required=false] A comma seperated list to
        show only results that ran with a script name, tag, or id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        script result object.
        @success-example "success-json" [exkey=script-results-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or script result is
        not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        script_set = self._get_script_set(request, system_id, id)
        include_output = get_optional_param(
            request.GET, "include_output", False, Bool
        )
        filters = get_optional_param(request.GET, "filters", None, String)
        if filters is not None:
            filters = filters.split(",")
        hardware_type = get_optional_param(request.GET, "hardware_type")
        if hardware_type is not None:
            try:
                hardware_type = translate_hardware_type(hardware_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)
        script_set.include_output = include_output
        script_set.filters = filters
        script_set.hardware_type = hardware_type
        return script_set

    @admin_method
    def delete(self, request, system_id, id):
        """@description-title Delete script results
        @description Delete script results from the given system_id with the
        given id.

        "id" can either by the script set id, ``current-commissioning``,
        ``current-testing``, or ``current-installation``.

        @param (string) "{system_id}" [required=true] The machine's system_id.
        @param (string) "{id}" [required=true] The script result id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or script result is
        not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        script_set = self._get_script_set(request, system_id, id)
        script_set.delete()
        return rc.DELETED

    def __make_file_title(self, script_result, filetype, extention=None):
        title = script_result.name
        if extention is not None:
            title = f"{title}.{extention}"

        if script_result.physical_blockdevice:
            if filetype == "txt":
                title = "{} - /dev/{}".format(
                    title,
                    script_result.physical_blockdevice.name,
                )
            else:
                title = "{}-{}".format(
                    title,
                    script_result.physical_blockdevice.name,
                )

        if script_result.interface:
            if filetype == "txt":
                title = f"{title} - {script_result.interface.name}"
            else:
                title = f"{title}-{script_result.interface.name}"

        return title

    @operation(idempotent=True)
    def download(self, request, system_id, id):
        """@description-title Download script results
        @description Download a compressed tar containing all results from the
        given system_id with the given id.

        "id" can either by the script set id, ``current-commissioning``,
        ``current-testing``, or ``current-installation``.

        @param (string) "{system_id}" [required=true] The machine's system_id.
        @param (string) "{id}" [required=true] The script result id.

        @param (string) "hardware_type" [required=false] Only return scripts
        for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or
        ``storage``.  Defaults to all.

        @param (string) "filters" [required=false] A comma seperated list to
        show only results that ran with a script name or tag.

        @param (string) "output" [required=false] Can be either ``combined``,
        ``stdout``, ``stderr``, or ``all``. By default only the combined output
        is returned.

        @param (string) "filetype" [required=false] Filetype to output, can be
        ``txt`` or ``tar.xz``.

        @success (http-status-code) "server-success" 200
        @success (content) "success-text" Plain-text output containing the
        requested results.
        @success-example "success-text" [exkey=script-results-download]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or script result is
        not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        script_set = self._get_script_set(request, system_id, id)
        filters = get_optional_param(request.GET, "filters", None, String)
        output = get_optional_param(request.GET, "output", "combined", String)
        filetype = get_optional_param(request.GET, "filetype", "txt", String)
        files = OrderedDict()
        times = {}
        if filters is not None:
            filters = filters.split(",")
        hardware_type = get_optional_param(request.GET, "hardware_type")
        if hardware_type is not None:
            try:
                hardware_type = translate_hardware_type(hardware_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)

        bin_regex = re.compile(r".+\.tar(\..+)?")
        for script_result in filter_script_results(
            script_set, filters, hardware_type
        ):
            mtime = time.mktime(script_result.updated.timetuple())
            if bin_regex.search(script_result.name) is not None:
                # Binary files only have one output
                files[script_result.name] = script_result.output
                times[script_result.name] = mtime
            elif output == "combined":
                title = self.__make_file_title(script_result, filetype)
                files[title] = script_result.output
                times[title] = mtime
            elif output == "stdout":
                title = self.__make_file_title(script_result, filetype, "out")
                files[title] = script_result.stdout
                times[title] = mtime
            elif output == "stderr":
                title = self.__make_file_title(script_result, filetype, "err")
                files[title] = script_result.stderr
                times[title] = mtime
            elif output == "result":
                title = self.__make_file_title(script_result, filetype, "yaml")
                files[title] = script_result.result
                times[title] = mtime
            elif output == "all":
                title = self.__make_file_title(script_result, filetype)
                files[title] = script_result.output
                times[title] = mtime
                title = self.__make_file_title(script_result, filetype, "out")
                files[title] = script_result.stdout
                times[title] = mtime
                title = self.__make_file_title(script_result, filetype, "err")
                files[title] = script_result.stderr
                times[title] = mtime
                title = self.__make_file_title(script_result, filetype, "yaml")
                files[title] = script_result.result
                times[title] = mtime

        if filetype == "txt" and len(files) == 1:
            # Just output the result with no break to allow for piping.
            return HttpResponse(
                list(files.values())[0], content_type="application/binary"
            )
        elif filetype == "txt":
            binary = BytesIO()
            for filename, content in files.items():
                dashes = "-" * int((80.0 - (2 + len(filename))) / 2)
                binary.write((f"{dashes} {filename} {dashes}\n").encode())
                if bin_regex.search(filename) is not None:
                    binary.write(b"Binary file")
                else:
                    binary.write(content)
                binary.write(b"\n")
            return HttpResponse(
                binary.getvalue(), content_type="application/binary"
            )
        elif filetype == "tar.xz":
            binary = BytesIO()
            root_dir = "{}-{}-{}".format(
                script_set.node.hostname,
                script_set.result_type_name.lower(),
                script_set.id,
            )
            with tarfile.open(mode="w:xz", fileobj=binary) as tar:
                for filename, content in files.items():
                    tarinfo = tarfile.TarInfo(
                        name=os.path.join(root_dir, os.path.basename(filename))
                    )
                    tarinfo.size = len(content)
                    tarinfo.mode = 0o644
                    tarinfo.mtime = times[filename]
                    tar.addfile(tarinfo, BytesIO(content))
            return HttpResponse(
                binary.getvalue(), content_type="application/x-tar"
            )
        else:
            raise MAASAPIValidationError(
                'Unknown filetype "%s" must be txt or tar.xz' % filetype
            )

    @admin_method
    def update(self, request, system_id, id):
        """@description-title Update specific script result
        @description Update a set of test results for a given system_id and
        script id.

        "id" can either be the script set id, ``current-commissioning``,
        ``current-testing``, or ``current-installation``.

        @param (string) "{system_id}" [required=true] The machine's system_id.
        @param (string) "{id}" [required=true] The script result id.

        @param (string) "hardware_type" [required=false] Only return scripts
        for the given hardware type.  Can be ``node``, ``cpu``, ``memory``, or
        ``storage``.  Defaults to all.

        @param (string) "filters" [required=false] A comma seperated list to
        show only results that ran with a script name, tag, or id.

        @param (string) "include_output" [required=false] Include the base64
        encoded output from the script if any value for include_output is
        given.

        @param (boolean) "suppressed" [required=false] Set whether or not
        this script result should be suppressed using 'true' or 'false'.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        script result object.
        @success-example "success-json" [exkey=script-results-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested machine or script result is
        not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        script_set = self._get_script_set(request, system_id, id)
        include_output = get_optional_param(
            request.PUT, "include_output", False, Bool
        )
        filters = get_optional_param(request.PUT, "filters", None, String)
        if filters is not None:
            filters = filters.split(",")
        hardware_type = get_optional_param(request.PUT, "hardware_type")
        if hardware_type is not None:
            try:
                hardware_type = translate_hardware_type(hardware_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)
        script_set.include_output = include_output
        script_set.filters = filters
        script_set.hardware_type = hardware_type
        suppressed = get_optional_param(
            request.data, "suppressed", None, StringBool
        )
        # Set the suppressed flag for the script results.
        if suppressed is not None:
            for script_result in filter_script_results(
                script_set, filters, hardware_type
            ):
                script_result.suppressed = suppressed
                script_result.save()
        return script_set

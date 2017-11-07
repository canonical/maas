# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `ScriptResults`."""

__all__ = [
    'NodeScriptResultHandler',
    'NodeScriptResultsHandler',
    ]

from base64 import b64encode
from collections import OrderedDict
from email.utils import format_datetime
from io import BytesIO
import os
import tarfile
import time

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from formencode.validators import (
    Bool,
    String,
)
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_optional_param
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import MAASAPIValidationError
from maasserver.models import Node
from metadataserver.models import ScriptSet
from metadataserver.models.script import translate_hardware_type
from metadataserver.models.scriptset import translate_result_type
from piston3.utils import rc


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
                if (f == script_result.name or f in tags or
                        (f.isdigit() and int(f) == script_result.id)):
                    script_results.append(script_result)
    if hardware_type is not None:
        script_results = [
            script_result for script_result in script_results
            if script_result.script is not None and
            script_result.script.hardware_type == hardware_type
        ]
    return sorted(script_results, key=lambda script_result: script_result.name)


class NodeScriptResultsHandler(OperationsHandler):
    """Manage node script results."""
    api_doc_section_name = "Node Script Result"

    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('script_results_handler', ['system_id'])

    def read(self, request, system_id):
        """Return a list of script results grouped by run.

        :param type: Only return scripts with the given type. This can be
                     commissioning, testing, or installion. Defaults to showing
                     all.
        :type type: unicode

        :param hardware_type: Only return scripts for the given hardware type.
            Can be node, cpu, memory, or storage. Defaults to all.
        :type script_type: unicode

        :param include_output: Include base64 encoded output from the script.
        :type include_output: bool

        :param filters: A comma seperated list to show only results
                        with a script name or tag.
        :type filters: unicode
        """
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.VIEW)
        result_type = get_optional_param(request.GET, 'type')
        include_output = get_optional_param(
            request.GET, 'include_output', False, Bool)
        filters = get_optional_param(request.GET, 'filters', None, String)
        if filters is not None:
            filters = filters.split(',')
        if result_type is not None:
            try:
                result_type = translate_result_type(result_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)
            else:
                qs = ScriptSet.objects.filter(
                    node=node, result_type=result_type)
        else:
            qs = ScriptSet.objects.filter(node=node)

        hardware_type = get_optional_param(request.GET, 'hardware_type')
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
        'id',
        'system_id',
        'type',
        'type_name',
        'last_ping',
        'status',
        'status_name',
        'started',
        'ended',
        'runtime',
        'results',
    )

    model = ScriptSet

    create = update = None

    @classmethod
    def resource_uri(cls, script_set=None):
        # See the comment in NodeHandler.resource_uri.
        if script_set is None:
            system_id = 'system_id'
            script_set_id = 'id'
        else:
            system_id = script_set.node.system_id
            script_set_id = script_set.id
        return ('script_result_handler', [system_id, script_set_id])

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
                script_set, script_set.filters, script_set.hardware_type):
            result = {
                'id': script_result.id,
                'created': format_datetime(script_result.created),
                'updated': format_datetime(script_result.updated),
                'name': script_result.name,
                'status': script_result.status,
                'status_name': script_result.status_name,
                'exit_status': script_result.exit_status,
                'started': fmt_time(script_result.started),
                'ended': fmt_time(script_result.ended),
                'runtime': script_result.runtime,
                'starttime': script_result.starttime,
                'endtime': script_result.endtime,
                'estimated_runtime': script_result.estimated_runtime,
                'parameters': script_result.parameters,
                'script_id': script_result.script_id,
                'script_revision_id': script_result.script_version_id,
            }
            if script_set.include_output:
                result['output'] = b64encode(script_result.output)
                result['stdout'] = b64encode(script_result.stdout)
                result['stderr'] = b64encode(script_result.stderr)
                result['result'] = b64encode(script_result.result)
            results.append(result)
        return results

    def _get_script_set(self, request, system_id, id):
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.VIEW)
        script_sets = {
            'current-commissioning': node.current_commissioning_script_set,
            'current-testing': node.current_testing_script_set,
            'current-installation': node.current_installation_script_set,
        }
        script_set = script_sets.get(id)
        if script_set is None and not id.isdigit():
            raise MAASAPIValidationError(
                'Unknown id "%s" must be current-commissioning, '
                'current-testing, current-installation, or the id number of a '
                'specific result.' % id)
        elif script_set is None:
            return get_object_or_404(ScriptSet, id=id, node=node)
        else:
            return script_set

    def read(self, request, system_id, id):
        """View a specific set of results.

        id can either by the script set id, current-commissioning,
        current-testing, or current-installation.

        :param hardware_type: Only return scripts for the given hardware type.
            Can be node, cpu, memory, or storage. Defaults to all.
        :type script_type: unicode

        :param include_output: Include base64 encoded output from the script.
        :type include_output: bool

        :param filters: A comma seperated list to show only results that ran
                        with a script name, tag, or id.
        :type filters: unicode
        """
        script_set = self._get_script_set(request, system_id, id)
        include_output = get_optional_param(
            request.GET, 'include_output', False, Bool)
        filters = get_optional_param(request.GET, 'filters', None, String)
        if filters is not None:
            filters = filters.split(',')
        hardware_type = get_optional_param(request.GET, 'hardware_type')
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
        """Delete a set of results.

        id can either by the script set id, current-commissioning,
        current-testing, or current-installation.
        """
        script_set = self._get_script_set(request, system_id, id)
        script_set.delete()
        return rc.DELETED

    @operation(idempotent=True)
    def download(self, request, system_id, id):
        """Download a compressed tar containing all results.

        id can either by the script set id, current-commissioning,
        current-testing, or current-installation.

        :param hardware_type: Only return scripts for the given hardware type.
            Can be node, cpu, memory, or storage. Defaults to all.
        :type script_type: unicode

        :param filters: A comma seperated list to show only results that ran
                        with a script name or tag.
        :type filters: unicode

        :param output: Can be either combined, stdout, stderr, or all. By
                       default only the combined output is returned.
        :type output: unicode

        :param filetype: Filetype to output, can be txt or tar.xz
        :type format: unicode
        """
        script_set = self._get_script_set(request, system_id, id)
        filters = get_optional_param(request.GET, 'filters', None, String)
        output = get_optional_param(request.GET, 'output', 'combined', String)
        filetype = get_optional_param(request.GET, 'filetype', 'txt', String)
        files = OrderedDict()
        times = {}
        if filters is not None:
            filters = filters.split(',')
        hardware_type = get_optional_param(request.GET, 'hardware_type')
        if hardware_type is not None:
            try:
                hardware_type = translate_hardware_type(hardware_type)
            except ValidationError as e:
                raise MAASAPIValidationError(e)

        for script_result in filter_script_results(
                script_set, filters, hardware_type):
            mtime = time.mktime(script_result.updated.timetuple())
            if output == 'combined':
                files[script_result.name] = script_result.output
                times[script_result.name] = mtime
            elif output == 'stdout':
                filename = '%s.out' % script_result.name
                files[filename] = script_result.stdout
                times[filename] = mtime
            elif output == 'stderr':
                filename = '%s.err' % script_result.name
                files[filename] = script_result.stderr
                times[filename] = mtime
            elif output == 'result':
                filename = '%s.yaml' % script_result.name
                files[filename] = script_result.result
                times[filename] = mtime
            elif output == 'all':
                files[script_result.name] = script_result.output
                times[script_result.name] = mtime
                filename = '%s.out' % script_result.name
                files[filename] = script_result.stdout
                times[filename] = mtime
                filename = '%s.err' % script_result.name
                files[filename] = script_result.stderr
                times[filename] = mtime
                filename = '%s.yaml' % script_result.name
                files[filename] = script_result.result
                times[filename] = mtime

        if filetype == 'txt' and len(files) == 1:
            # Just output the result with no break to allow for piping.
            return HttpResponse(
                list(files.values())[0], content_type='application/binary')
        elif filetype == 'txt':
            binary = BytesIO()
            for filename, content in files.items():
                dashes = '-' * int((80.0 - (2 + len(filename))) / 2)
                binary.write(
                    ('%s %s %s\n' % (dashes, filename, dashes)).encode())
                binary.write(content)
                binary.write(b'\n')
            return HttpResponse(
                binary.getvalue(), content_type='application/binary')
        elif filetype == 'tar.xz':
            binary = BytesIO()
            root_dir = '%s-%s-%s' % (
                script_set.node.hostname, script_set.result_type_name.lower(),
                script_set.id)
            with tarfile.open(mode='w:xz', fileobj=binary) as tar:
                for filename, content in files.items():
                    tarinfo = tarfile.TarInfo(
                        name=os.path.join(root_dir, filename))
                    tarinfo.size = len(content)
                    tarinfo.mode = 0o644
                    tarinfo.mtime = times[filename]
                    tar.addfile(tarinfo, BytesIO(content))
            return HttpResponse(
                binary.getvalue(), content_type='application/x-tar')
        else:
            raise MAASAPIValidationError(
                'Unknown filetype "%s" must be txt or tar.xz' % filetype)

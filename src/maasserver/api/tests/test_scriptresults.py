# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the script result API."""

__all__ = []

from base64 import b64encode
import http.client
from io import BytesIO
import os
import random
import tarfile
import time

from maasserver.api.scriptresults import fmt_time
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.testing.matchers import HasStatusCode
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.django_urls import reverse
from maasserver.utils.orm import reload_object
from metadataserver.enum import RESULT_TYPE


class TestNodeScriptResultsAPI(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/<system_id>/results/."""

    @staticmethod
    def get_script_results_uri(node):
        """Return the script's URI on the API."""
        return reverse('script_results_handler', args=[node.system_id])

    def test_hander_path(self):
        node = factory.make_Node()
        self.assertEqual(
            '/api/2.0/nodes/%s/results/' % node.system_id,
            self.get_script_results_uri(node))

    def test_GET(self):
        node = factory.make_Node()
        script_set_ids = []
        for _ in range(3):
            script_set = factory.make_ScriptSet(node=node)
            script_set_ids.append(script_set.id)
            for _ in range(3):
                factory.make_ScriptResult(script_set=script_set)

        # Script sets for different nodes.
        for _ in range(3):
            factory.make_ScriptSet()

        response = self.client.get(self.get_script_results_uri(node))
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertItemsEqual(
            script_set_ids,
            [result['id'] for result in parsed_results])
        for script_set in parsed_results:
            for result in script_set['results']:
                self.assertNotIn('output', result)
                self.assertNotIn('stdout', result)
                self.assertNotIn('stderr', result)

    def test_GET_filters_by_type(self):
        node = factory.make_Node()
        script_sets = [
            {
                'names': [
                    RESULT_TYPE.COMMISSIONING, 'commission', 'commissioning'],
                'script_set_ids': [
                    factory.make_ScriptSet(
                        node=node, result_type=RESULT_TYPE.COMMISSIONING).id
                    for _ in range(3)],
            },
            {
                'names': [
                    RESULT_TYPE.TESTING, 'test', 'testing'],
                'script_set_ids': [
                    factory.make_ScriptSet(
                        node=node, result_type=RESULT_TYPE.TESTING).id
                    for _ in range(3)],
            },
            {
                'names': [
                    RESULT_TYPE.INSTALLATION, 'install', 'installation'],
                'script_set_ids': [
                    factory.make_ScriptSet(
                        node=node, result_type=RESULT_TYPE.INSTALLATION).id
                    for _ in range(3)],
            },
        ]
        # Script sets for different nodes.
        for _ in range(10):
            factory.make_ScriptSet()

        for script_set in script_sets:
            for name in script_set['names']:
                response = self.client.get(
                    self.get_script_results_uri(node), {'type': name})
                self.assertThat(response, HasStatusCode(http.client.OK))
                parsed_results = json_load_bytes(response.content)

                self.assertItemsEqual(
                    script_set['script_set_ids'],
                    [result['id'] for result in parsed_results])

    def test_GET_include_output(self):
        node = factory.make_Node()
        script_set_ids = []
        for _ in range(3):
            script_set = factory.make_ScriptSet(node=node)
            script_set_ids.append(script_set.id)
            for _ in range(3):
                factory.make_ScriptResult(script_set=script_set)

        # Script sets for different nodes.
        for _ in range(3):
            factory.make_ScriptSet()

        response = self.client.get(
            self.get_script_results_uri(node),
            {'include_output': True})
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertItemsEqual(
            script_set_ids,
            [result['id'] for result in parsed_results])
        for script_set in parsed_results:
            for result in script_set['results']:
                self.assertIn('output', result)
                self.assertIn('stdout', result)
                self.assertIn('stderr', result)

    def test_GET_filters(self):
        node = factory.make_Node()
        scripts = [factory.make_Script() for _ in range(3)]
        name_filter_script = random.choice(scripts)
        tag_filter_script = random.choice(scripts)
        script_set_ids = []
        for _ in range(3):
            script_set = factory.make_ScriptSet(node=node)
            script_set_ids.append(script_set.id)
            for script in scripts:
                factory.make_ScriptResult(script_set=script_set, script=script)

        # Script sets for different nodes.
        for _ in range(3):
            factory.make_ScriptSet()

        response = self.client.get(
            self.get_script_results_uri(node),
            {'filters': ','.join([
                name_filter_script.name,
                random.choice(tag_filter_script.tags)])})
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_results = json_load_bytes(response.content)

        self.assertItemsEqual(
            script_set_ids,
            [result['id'] for result in parsed_results])
        for script_set in parsed_results:
            for result in script_set['results']:
                self.assertIn(
                    result['name'],
                    {name_filter_script.name, tag_filter_script.name})
                self.assertNotIn('output', result)
                self.assertNotIn('stdout', result)
                self.assertNotIn('stderr', result)


class TestNodeScriptResultAPI(APITestCase.ForUser):
    """Tests for /api/2.0/nodes/<system_id>/results/<id>."""

    scenarios = (
        ('id', {
            'id_value': None,
            'key': None,
            }),
        ('commissioning', {
            'id_value': 'current-commissioning',
            'key': 'current_commissioning_script_set',
            }),
        ('testing', {
            'id_value': 'current-testing',
            'key': 'current_testing_script_set',
            }),
        ('installation', {
            'id_value': 'current-installation',
            'key': 'current_installation_script_set',
            }),
    )

    def get_script_result_uri(self, script_set):
        """Return the script's URI on the API."""
        return reverse(
            'script_result_handler',
            args=[script_set.node.system_id, self.get_id(script_set)])

    def make_scriptset(self, *args, **kwargs):
        script_set = factory.make_ScriptSet(*args, **kwargs)
        if self.key is not None:
            setattr(script_set.node, self.key, script_set)
            script_set.node.save()
        return script_set

    def get_id(self, script_set):
        if self.id_value is None:
            return script_set.id
        else:
            return self.id_value

    def test_hander_path(self):
        script_set = self.make_scriptset()
        self.assertEqual(
            '/api/2.0/nodes/%s/results/%s/' % (
                script_set.node.system_id, self.get_id(script_set)),
            self.get_script_result_uri(script_set))

    def test_GET(self):
        script_set = self.make_scriptset()
        script_results = {}
        for _ in range(3):
            script_result = factory.make_ScriptResult(script_set=script_set)
            script_results[script_result.name] = script_result

        response = self.client.get(self.get_script_result_uri(script_set))
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop('results')

        self.assertDictEqual({
            'id': script_set.id,
            'system_id': script_set.node.system_id,
            'type': script_set.result_type,
            'type_name': script_set.result_type_name,
            'last_ping': fmt_time(script_set.last_ping),
            'status': script_set.status,
            'status_name': script_set.status_name,
            'started': fmt_time(script_set.started),
            'ended': fmt_time(script_set.ended),
            'runtime': script_set.runtime,
            'resource_uri': '/api/2.0/nodes/%s/results/%d/' % (
                script_set.node.system_id, script_set.id),
            }, parsed_result)
        for result in results:
            script_result = script_results[result['name']]
            self.assertDictEqual({
                'id': script_result.id,
                'name': script_result.name,
                'created': fmt_time(script_result.created),
                'updated': fmt_time(script_result.updated),
                'status': script_result.status,
                'status_name': script_result.status_name,
                'exit_status': script_result.exit_status,
                'started': fmt_time(script_result.started),
                'ended': fmt_time(script_result.ended),
                'runtime': script_result.runtime,
                'script_id': script_result.script_id,
                'script_revision_id': script_result.script_version_id,
                }, result)

    def test_GET_include_output(self):
        script_set = self.make_scriptset()
        script_results = {}
        for _ in range(3):
            script_result = factory.make_ScriptResult(script_set=script_set)
            script_results[script_result.name] = script_result

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {'include_output': True})
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop('results')

        self.assertDictEqual({
            'id': script_set.id,
            'system_id': script_set.node.system_id,
            'type': script_set.result_type,
            'type_name': script_set.result_type_name,
            'last_ping': fmt_time(script_set.last_ping),
            'status': script_set.status,
            'status_name': script_set.status_name,
            'started': fmt_time(script_set.started),
            'ended': fmt_time(script_set.ended),
            'runtime': script_set.runtime,
            'resource_uri': '/api/2.0/nodes/%s/results/%d/' % (
                script_set.node.system_id, script_set.id),
            }, parsed_result)
        for result in results:
            script_result = script_results[result['name']]
            self.assertDictEqual({
                'id': script_result.id,
                'name': script_result.name,
                'created': fmt_time(script_result.created),
                'updated': fmt_time(script_result.updated),
                'status': script_result.status,
                'status_name': script_result.status_name,
                'exit_status': script_result.exit_status,
                'started': fmt_time(script_result.started),
                'ended': fmt_time(script_result.ended),
                'runtime': script_result.runtime,
                'script_id': script_result.script_id,
                'script_revision_id': script_result.script_version_id,
                'output': b64encode(script_result.output).decode(),
                'stdout': b64encode(script_result.stdout).decode(),
                'stderr': b64encode(script_result.stderr).decode(),
                }, result)

    def test_GET_filters(self):
        scripts = [factory.make_Script() for _ in range(10)]
        script_set = self.make_scriptset()
        script_results = {}
        for script in scripts:
            script_result = factory.make_ScriptResult(
                script_set=script_set, script=script)
            script_results[script_result.name] = script_result
        results_list = list(script_results.values())
        filtered_results = [random.choice(results_list) for _ in range(3)]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {'filters': '%s,%s,%d' % (
                filtered_results[0].name,
                random.choice(filtered_results[1].script.tags),
                filtered_results[2].id)})
        self.assertThat(response, HasStatusCode(http.client.OK))
        parsed_result = json_load_bytes(response.content)
        results = parsed_result.pop('results')

        self.assertDictEqual({
            'id': script_set.id,
            'system_id': script_set.node.system_id,
            'type': script_set.result_type,
            'type_name': script_set.result_type_name,
            'last_ping': fmt_time(script_set.last_ping),
            'status': script_set.status,
            'status_name': script_set.status_name,
            'started': fmt_time(script_set.started),
            'ended': fmt_time(script_set.ended),
            'runtime': script_set.runtime,
            'resource_uri': '/api/2.0/nodes/%s/results/%d/' % (
                script_set.node.system_id, script_set.id),
            }, parsed_result)
        for result in results:
            self.assertIn(
                result['name'],
                [script_result.name for script_result in filtered_results])
            script_result = script_results[result['name']]
            self.assertDictEqual({
                'id': script_result.id,
                'name': script_result.name,
                'created': fmt_time(script_result.created),
                'updated': fmt_time(script_result.updated),
                'status': script_result.status,
                'status_name': script_result.status_name,
                'exit_status': script_result.exit_status,
                'started': fmt_time(script_result.started),
                'ended': fmt_time(script_result.ended),
                'runtime': script_result.runtime,
                'script_id': script_result.script_id,
                'script_revision_id': script_result.script_version_id,
                }, result)

    def test_DELETE(self):
        # Users are unable to delete the current-commissioning or
        # current-installation script sets.
        if self.id_value in ('current-commissioning', 'current-installation'):
            return
        self.become_admin()
        script_set = self.make_scriptset()
        response = self.client.delete(self.get_script_result_uri(script_set))
        self.assertThat(response, HasStatusCode(http.client.NO_CONTENT))
        self.assertIsNone(reload_object(script_set))

    def test_DELETE_admin_only(self):
        script_set = self.make_scriptset()
        response = self.client.delete(self.get_script_result_uri(script_set))
        self.assertThat(response, HasStatusCode(http.client.FORBIDDEN))
        self.assertIsNotNone(reload_object(script_set))

    def test_download(self):
        script_set = self.make_scriptset()
        script_results = [
            factory.make_ScriptResult(script_set=script_set)
            for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {'op': 'download'})
        self.assertThat(response, HasStatusCode(http.client.OK))

        binary = BytesIO()
        for script_result in sorted(
                list(script_results),
                key=lambda script_result: script_result.name):
            dashes = '-' * int((80.0 - (2 + len(script_result.name))) / 2)
            binary.write(
                ('%s %s %s\n' % (dashes, script_result.name, dashes)).encode())
            binary.write(script_result.output)
            binary.write(b'\n')
        self.assertEquals(binary.getvalue(), response.content)

    def test_download_single(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filter': script_result.id,
            })
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertEquals(script_result.output, response.content)

    def test_download_filetype_txt(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filetype': 'txt',
                'filters': script_result.id,
            })
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertEquals(script_result.output, response.content)

    def test_download_filetype_tar_xz(self):
        script_set = self.make_scriptset()
        script_results = [
            factory.make_ScriptResult(script_set=script_set)
            for _ in range(3)
        ]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filetype': 'tar.xz',
            })
        self.assertThat(response, HasStatusCode(http.client.OK))

        root_dir = '%s-%s-%s' % (
            script_set.node.hostname, script_set.result_type_name.lower(),
            script_set.id)
        with tarfile.open(mode='r', fileobj=BytesIO(response.content)) as tar:
            for script_result in script_results:
                path = os.path.join(root_dir, script_result.name)
                member = tar.getmember(path)
                self.assertEqual(
                    time.mktime(script_result.updated.timetuple()),
                    member.mtime)
                self.assertEqual(0o644, member.mode)
                self.assertEqual(
                    script_result.output, tar.extractfile(path).read())

    def test_download_filetype_unknown(self):
        script_set = self.make_scriptset()
        factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filetype': factory.make_name('filetype'),
            })
        self.assertThat(response, HasStatusCode(http.client.BAD_REQUEST))

    def test_download_output_combined(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filter': script_result.id,
                'output': 'combined',
            })
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertEquals(script_result.output, response.content)

    def test_download_output_stdout(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filter': script_result.id,
                'output': 'stdout',
            })
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertEquals(script_result.stdout, response.content)

    def test_download_output_stderr(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filter': script_result.id,
                'output': 'stderr',
            })
        self.assertThat(response, HasStatusCode(http.client.OK))
        self.assertEquals(script_result.stderr, response.content)

    def test_download_output_all(self):
        script_set = self.make_scriptset()
        script_result = factory.make_ScriptResult(script_set=script_set)

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filter': script_result.id,
                'output': 'all',
            })
        self.assertThat(response, HasStatusCode(http.client.OK))

        binary = BytesIO()
        dashes = '-' * int((80.0 - (2 + len(script_result.name))) / 2)
        binary.write(
            ('%s %s %s\n' % (dashes, script_result.name, dashes)).encode())
        binary.write(script_result.output)
        binary.write(b'\n')
        filename = '%s.out' % script_result.name
        dashes = '-' * int((80.0 - (2 + len(filename))) / 2)
        binary.write(('%s %s %s\n' % (dashes, filename, dashes)).encode())
        binary.write(script_result.stdout)
        binary.write(b'\n')
        filename = '%s.err' % script_result.name
        dashes = '-' * int((80.0 - (2 + len(filename))) / 2)
        binary.write(('%s %s %s\n' % (dashes, filename, dashes)).encode())
        binary.write(script_result.stderr)
        binary.write(b'\n')
        self.assertEquals(binary.getvalue(), response.content)

    def test_download_filters(self):
        scripts = [factory.make_Script() for _ in range(10)]
        script_set = self.make_scriptset()
        script_results = {}
        for script in scripts:
            script_result = factory.make_ScriptResult(
                script_set=script_set, script=script)
            script_results[script_result.name] = script_result
        results_list = list(script_results.values())
        filtered_results = [random.choice(results_list) for _ in range(3)]

        response = self.client.get(
            self.get_script_result_uri(script_set),
            {
                'op': 'download',
                'filetype': 'tar.xz',
                'filters': '%s,%s,%d' % (
                    filtered_results[0].name,
                    random.choice(filtered_results[1].script.tags),
                    filtered_results[2].id),
            })
        self.assertThat(response, HasStatusCode(http.client.OK))

        root_dir = '%s-%s-%s' % (
            script_set.node.hostname, script_set.result_type_name.lower(),
            script_set.id)
        with tarfile.open(mode='r', fileobj=BytesIO(response.content)) as tar:
            self.assertEquals(
                len(set(filtered_results)), len(tar.getmembers()))
            for script_result in filtered_results:
                path = os.path.join(root_dir, script_result.name)
                member = tar.getmember(path)
                self.assertEqual(
                    time.mktime(script_result.updated.timetuple()),
                    member.mtime)
                self.assertEqual(0o644, member.mode)
                self.assertEqual(
                    script_result.output, tar.extractfile(path).read())

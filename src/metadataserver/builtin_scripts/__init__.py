# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin scripts commited to Script model."""

__all__ = [
    'load_builtin_scripts',
]

import os

import attr
from attr.validators import (
    instance_of,
    optional,
)
from maasserver.forms.script import ScriptForm
from metadataserver.models import Script
from provisioningserver.utils.version import get_maas_version
import tempita
from zope.interface import (
    Attribute,
    implementer,
    Interface,
)
from zope.interface.verify import verifyObject


class IBuiltinScript(Interface):

    name = Attribute('Name')
    filename = Attribute('Filename')
    substitutes = Attribute('Substitutes')
    inject_file = Attribute('Inject File')


@implementer(IBuiltinScript)
@attr.s
class BuiltinScript:

    name = attr.ib(default=None, validator=instance_of(str))
    filename = attr.ib(default=None, validator=instance_of(str))
    substitutes = attr.ib(default={}, validator=optional(instance_of(dict)))
    inject_file = attr.ib(default=None, validator=optional(instance_of(str)))

    @property
    def script_path(self):
        return os.path.join(os.path.dirname(__file__), self.filename)

    @property
    def inject_path(self):
        return os.path.join(os.path.dirname(__file__), self.inject_file)


BUILTIN_SCRIPTS = [
    BuiltinScript(
        name='smartctl-validate',
        filename='smartctl.py',
        substitutes={
            'title': 'Storage status',
            'description': 'Validate SMART health for all drives in parallel.',
            'timeout': '00:05:00',
        }),
    BuiltinScript(
        name='smartctl-short',
        filename='smartctl.py',
        substitutes={
            'title': 'Storage integrity',
            'description': (
                'Run the short SMART self-test and validate SMART health on '
                'all drives in parallel'),
            'timeout': '00:10:00',
        }),
    BuiltinScript(
        name='smartctl-long',
        filename='smartctl.py',
        substitutes={
            'title': 'Storage integrity',
            'description': (
                'Run the long SMART self-test and validate SMART health on '
                'all drives in parallel'),
            'timeout': '00:00:00',
        }),
    BuiltinScript(
        name='smartctl-conveyance',
        filename='smartctl.py',
        substitutes={
            'title': 'Storage integrity',
            'description': (
                'Run the conveyance SMART self-test and validate SMART health '
                'on all drives in parallel'),
            'timeout': '00:00:00',
        }),
    BuiltinScript(
        name='memtester',
        filename='memtester.sh',
        ),
    BuiltinScript(
        name='stress-ng-cpu-long',
        filename='stress-ng-cpu-long.sh',
        ),
    BuiltinScript(
        name='stress-ng-cpu-short',
        filename='stress-ng-cpu-short.sh',
        ),
    BuiltinScript(
        name='stress-ng-memory-long',
        filename='stress-ng-memory-long.sh',
        ),
    BuiltinScript(
        name='stress-ng-memory-short',
        filename='stress-ng-memory-short.sh',
        ),
    BuiltinScript(
        name='ntp',
        filename='ntp.sh',
        ),
    BuiltinScript(
        name='badblocks',
        filename='badblocks.py',
        substitutes={
            'description': 'Run badblocks on disk in readonly mode.',
            },
        ),
    BuiltinScript(
        name='badblocks-destructive',
        filename='badblocks.py',
        substitutes={
            'description': (
                'Run badblocks on a disk in read/write destructive mode.'),
            },
        ),
    BuiltinScript(
        name='7z',
        filename='seven_z.py',
        ),
    BuiltinScript(
        name='fio',
        filename='fio.py',
        ),
    BuiltinScript(
        name='internet-connectivity',
        filename='internet-connectivity.sh',
        inject_file='base-connectivity.sh',
        ),
    BuiltinScript(
        name='gateway-connectivity',
        filename='gateway-connectivity.sh',
        inject_file='base-connectivity.sh',
        ),
    BuiltinScript(
        name='rack-controller-connectivity',
        filename='rack-controller-connectivity.sh',
        inject_file='base-connectivity.sh',
        ),
    ]


# The IBuiltinScript interface isn't necessary, but it does serve two
# purposes: it documents expectations for future implementors, and the
# verifyObject calls below give early feedback about missing pieces.
for script in BUILTIN_SCRIPTS:
    verifyObject(IBuiltinScript, script)


def load_builtin_scripts():
    for script in BUILTIN_SCRIPTS:
        if script.inject_file:
            with open(script.inject_path, 'r') as f:
                script.substitutes['inject_file'] = f.read()
        script_content = tempita.Template.from_filename(
            script.script_path, encoding='utf-8')
        script_content = script_content.substitute({
            'name': script.name,
            **script.substitutes,
            })
        try:
            script_in_db = Script.objects.get(name=script.name)
        except Script.DoesNotExist:
            form = ScriptForm(data={
                'script': script_content,
                'comment': "Created by maas-%s" % get_maas_version(),
            })
            # Form validation should never fail as these are the scripts which
            # ship with MAAS. If they ever do this will be cause by unit tests.
            if not form.is_valid():
                raise Exception("%s: %s" % (script.name, form.errors))
            script_in_db = form.save(commit=False)
            script_in_db.default = True
            script_in_db.save()
        else:
            if script_in_db.script.data != script_content:
                # Don't add back old versions of a script. This prevents two
                # connected regions with different versions of a script from
                # fighting with eachother.
                no_update = False
                for vtf in script_in_db.script.previous_versions():
                    if vtf.data == script_content:
                        # Don't update anything if we detect we have an old
                        # version of the builtin scripts
                        no_update = True
                        break
                if no_update:
                    continue
                form = ScriptForm(instance=script_in_db, data={
                    'script': script_content,
                    'comment': "Updated by maas-%s" % get_maas_version(),
                    }, edit_default=True)
                # Form validation should never fail as these are the scripts
                # which ship with MAAS. If they ever do this will be cause by
                # unit tests.
                if not form.is_valid():
                    raise Exception("%s: %s" % (script.name, form.errors))
                script_in_db = form.save(commit=False)
                script_in_db.default = True
                script_in_db.save()

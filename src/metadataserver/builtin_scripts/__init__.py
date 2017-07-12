# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin scripts commited to Script model."""

__all__ = [
    'load_builtin_scripts',
]

from datetime import timedelta
import os

import attr
from attr.validators import (
    instance_of,
    optional,
)
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.models import Script
from provisioningserver.utils.fs import read_text_file
from provisioningserver.utils.version import get_maas_version
from zope.interface import (
    Attribute,
    implementer,
    Interface,
)
from zope.interface.verify import verifyObject


class IBuiltinScript(Interface):

    name = Attribute('Name')
    title = Attribute('Title')
    description = Attribute('Description')
    tags = Attribute('Tags')
    script_type = Attribute('Script type')
    timeout = Attribute('Timeout')
    destructive = Attribute('Destructive')
    filename = Attribute('Filename')


@implementer(IBuiltinScript)
@attr.s
class BuiltinScript:

    name = attr.ib(default=None, validator=instance_of(str))
    title = attr.ib(default=None, validator=optional(instance_of(str)))
    description = attr.ib(default=None, validator=instance_of(str))
    tags = attr.ib(default=None, validator=instance_of(list))
    script_type = attr.ib(
        default=SCRIPT_TYPE.TESTING, validator=instance_of(int))
    timeout = attr.ib(
        default=timedelta(seconds=0), validator=instance_of(timedelta))
    destructive = attr.ib(default=False, validator=instance_of(bool))
    filename = attr.ib(default=None, validator=instance_of(str))

    @property
    def script_path(self):
        return os.path.join(os.path.dirname(__file__), self.filename)


BUILTIN_SCRIPTS = [
    BuiltinScript(
        name='smartctl-validate',
        title='Storage status',
        description='Validate SMART health for all drives in parallel.',
        tags=['storage', 'commissioning'],
        timeout=timedelta(minutes=5),
        filename='smartctl.py',
        ),
    BuiltinScript(
        name='smartctl-short',
        title='Storage integrity',
        description=(
            'Run the short SMART self-test and validate SMART health on all '
            'drives in parallel'),
        tags=['storage'],
        timeout=timedelta(minutes=10),
        filename='smartctl.py',
        ),
    BuiltinScript(
        name='smartctl-long',
        title='Storage integrity',
        description=(
            'Run the long SMART self-test and validate SMART health on all '
            'drives in parallel'),
        tags=['storage'],
        filename='smartctl.py',
        ),
    BuiltinScript(
        name='smartctl-conveyance',
        title='Storage integrity',
        description=(
            'Run the conveyance SMART self-test and validate SMART health on '
            'all drives in parallel'),
        tags=['storage'],
        filename='smartctl.py',
        ),
    BuiltinScript(
        name='memtester',
        title='Memory integrity',
        description='Run memtester against all available RAM.',
        tags=['memory'],
        filename='memtester.sh',
        ),
    BuiltinScript(
        name='internet-connectivity',
        title='Network validation',
        description='Download a file from images.maas.io.',
        tags=['network', 'internet'],
        timeout=timedelta(minutes=5),
        filename='internet_connectivity.sh',
        ),
    BuiltinScript(
        name='stress-ng-cpu-long',
        title='CPU validation',
        description='Run the stress-ng CPU tests over 12 hours.',
        tags=['cpu'],
        timeout=timedelta(hours=12),
        filename='stress-ng-cpu-long.sh',
        ),
    BuiltinScript(
        name='stress-ng-cpu-short',
        title='CPU validation',
        description='Stress test the CPU for 5 minutes.',
        tags=['cpu'],
        timeout=timedelta(minutes=5),
        filename='stress-ng-cpu-short.sh',
        ),
    BuiltinScript(
        name='stress-ng-memory-long',
        title='Memory integrity',
        description='Run the stress-ng memory tests over 12 hours.',
        tags=['memory'],
        timeout=timedelta(hours=12),
        filename='stress-ng-memory-long.sh',
        ),
    BuiltinScript(
        name='stress-ng-memory-short',
        title='Memory validation',
        description='Stress test memory for 5 minutes.',
        tags=['memory'],
        timeout=timedelta(minutes=5),
        filename='stress-ng-memory-short.sh',
        ),
    BuiltinScript(
        name='ntp',
        title='NTP validation',
        description='Run ntp clock set to verify NTP connectivity.',
        tags=['network', 'ntp'],
        timeout=timedelta(minutes=1),
        filename='ntp.sh',
        ),
    BuiltinScript(
        name='badblocks',
        title='Storage integrity',
        description=(
            'Run badblocks readonly tests against all drives in parallel.'),
        tags=['storage'],
        filename='badblocks.py',
        ),
    BuiltinScript(
        name='badblocks-destructive',
        title='Storage integrity',
        description=(
            'Run badblocks destructive tests against all drives in parallel.'),
        tags=['storage'],
        filename='badblocks.py',
        destructive=True,
        ),
]


# The IBuiltinScript interface isn't necessary, but it does serve two
# purposes: it documents expectations for future implementors, and the
# verifyObject calls below give early feedback about missing pieces.
for script in BUILTIN_SCRIPTS:
    verifyObject(IBuiltinScript, script)


def load_builtin_scripts():
    for script in BUILTIN_SCRIPTS:
        script_content = read_text_file(script.script_path)
        try:
            script_in_db = Script.objects.get(name=script.name)
        except Script.DoesNotExist:
            Script.objects.create(
                name=script.name, title=script.title,
                description=script.description, tags=script.tags,
                script_type=script.script_type, script=script_content,
                comment="Created by maas-%s" % get_maas_version(),
                timeout=script.timeout, destructive=script.destructive,
                default=True)
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
                script_in_db.script = script_in_db.script.update(
                    script_content,
                    "Updated by maas-%s" % get_maas_version())
            script_in_db.title = script.title
            script_in_db.description = script.description
            script_in_db.script_type = script.script_type
            script_in_db.destructive = script.destructive
            script_in_db.save()

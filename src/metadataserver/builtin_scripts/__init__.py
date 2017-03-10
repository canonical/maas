# Copyright 2017 Canonical Ltd.  This software is licensed under the
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
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.models import Script
from provisioningserver.utils.fs import read_text_file
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
    timeout = attr.ib(default=0, validator=instance_of(int))
    destructive = attr.ib(default=False, validator=instance_of(bool))
    filename = attr.ib(default=None, validator=instance_of(str))

    @property
    def script_path(self):
        return os.path.join(os.path.dirname(__file__), self.filename)


BUILTIN_SCRIPTS = [
    BuiltinScript(
        name='smartctl-validate',
        title='Storage Status',
        description='Validate SMART health for all drives in parellel.',
        tags=['storage', 'commissioning'],
        timeout=60 * 5,
        filename='smartctl.py',
        ),
    BuiltinScript(
        name='smartctl-short',
        title='Storage Integrity',
        description=(
            'Run the short SMART self-test and validate SMART health on all '
            'drives in parellel'),
        tags=['storage'],
        timeout=60 * 10,
        filename='smartctl.py',
        ),
    BuiltinScript(
        name='smartctl-long',
        title='Storage Integrity',
        description=(
            'Run the long SMART self-test and validate SMART health on all '
            'drives in parellel'),
        tags=['storage'],
        filename='smartctl.py',
        ),
    BuiltinScript(
        name='smartctl-conveyance',
        title='Storage Integrity',
        description=(
            'Run the conveyance SMART self-test and validate SMART health on '
            'all drives in parellel'),
        tags=['storage'],
        filename='smartctl.py',
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
                timeout=script.timeout, destructive=script.destructive,
                default=True)
        else:
            if script_in_db.script.data != script_content:
                # Don't add back old versions of a script. This prevents two
                # connected regions with different versions of a script from
                # fighting with eachother.
                for vtf in script_in_db.script.previous_versions():
                    if vtf.data == script_content:
                        # Don't update anything if we detect we have an old
                        # version of the builtin scripts
                        return
                script_in_db.script = script_in_db.script.update(
                    script_content)
            script_in_db.title = script.title
            script_in_db.description = script.description
            script_in_db.script_type = script.script_type
            script_in_db.destructive = script.destructive
            script_in_db.save()

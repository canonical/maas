# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin scripts commited to Script model."""


import os

import attr
from attr.validators import instance_of, optional
import tempita
from zope.interface import Attribute, implementer, Interface
from zope.interface.verify import verifyObject

from maasserver.forms.script import ScriptForm
from maasserver.models.controllerinfo import get_maas_version
from maasserver.models.script import Script
from provisioningserver.refresh.node_info_scripts import (
    BMC_DETECTION,
    COMMISSIONING_OUTPUT_NAME,
    DHCP_EXPLORE_OUTPUT_NAME,
    GET_FRUID_DATA_OUTPUT_NAME,
    KERNEL_CMDLINE_OUTPUT_NAME,
    LIST_MODALIASES_OUTPUT_NAME,
    LLDP_INSTALL_OUTPUT_NAME,
    LLDP_OUTPUT_NAME,
    LSHW_OUTPUT_NAME,
    MACHINE_CONFIG_HINTS_NAME,
    NODE_INFO_SCRIPTS,
    RUN_MACHINE_RESOURCES,
    SERIAL_PORTS_OUTPUT_NAME,
    SUPPORT_INFO_OUTPUT_NAME,
)


class IBuiltinScript(Interface):
    name = Attribute("Name")
    filename = Attribute("Filename")
    substitutes = Attribute("Substitutes")
    inject_file = Attribute("Inject File")


@implementer(IBuiltinScript)
@attr.s
class BuiltinScript:
    name = attr.ib(default=None, validator=instance_of(str))
    filename = attr.ib(default=None, validator=instance_of(str))
    substitutes = attr.ib(default={}, validator=optional(instance_of(dict)))
    inject_file = attr.ib(default=None, validator=optional(instance_of(str)))

    def _find_file(self, filename):
        base_path = os.path.dirname(__file__)
        for search_path in {
            os.path.join(base_path, "commissioning_scripts"),
            os.path.join(base_path, "testing_scripts"),
            # Controllers run a subset of commissioning scripts but don't
            # have the ability to download commissioning scripts from the
            # metadata server. Since rack controllers can be installed
            # without a region controller these scripts must be stored
            # in the rack's source tree.
            os.path.join(base_path, "../../provisioningserver/refresh"),
        }:
            path = os.path.realpath(os.path.join(search_path, filename))
            if os.path.exists(path):
                return path
        # This should never happen and will be caught by multiple unit tests.
        raise FileNotFoundError(filename)

    @property
    def script_path(self):
        return self._find_file(self.filename)

    @property
    def inject_path(self):
        return self._find_file(self.inject_file)


BUILTIN_SCRIPTS = [
    # Commissioning scripts
    BuiltinScript(name=LLDP_INSTALL_OUTPUT_NAME, filename="install_lldpd.py"),
    BuiltinScript(
        name=DHCP_EXPLORE_OUTPUT_NAME, filename="dhcp_unconfigured_ifaces.py"
    ),
    BuiltinScript(name=BMC_DETECTION, filename="bmc_config.py"),
    BuiltinScript(name=RUN_MACHINE_RESOURCES, filename=RUN_MACHINE_RESOURCES),
    BuiltinScript(
        name=MACHINE_CONFIG_HINTS_NAME, filename=MACHINE_CONFIG_HINTS_NAME
    ),
    BuiltinScript(
        name=COMMISSIONING_OUTPUT_NAME, filename=COMMISSIONING_OUTPUT_NAME
    ),
    BuiltinScript(
        name=SUPPORT_INFO_OUTPUT_NAME, filename=SUPPORT_INFO_OUTPUT_NAME
    ),
    BuiltinScript(name=LSHW_OUTPUT_NAME, filename=LSHW_OUTPUT_NAME),
    BuiltinScript(
        name=LIST_MODALIASES_OUTPUT_NAME,
        filename=LIST_MODALIASES_OUTPUT_NAME,
    ),
    BuiltinScript(
        name=GET_FRUID_DATA_OUTPUT_NAME,
        filename=GET_FRUID_DATA_OUTPUT_NAME,
    ),
    BuiltinScript(
        name=KERNEL_CMDLINE_OUTPUT_NAME,
        filename=KERNEL_CMDLINE_OUTPUT_NAME,
    ),
    BuiltinScript(
        name=SERIAL_PORTS_OUTPUT_NAME, filename=SERIAL_PORTS_OUTPUT_NAME
    ),
    BuiltinScript(name=LLDP_OUTPUT_NAME, filename="capture_lldpd.py"),
    # Testing scripts
    BuiltinScript(
        name="smartctl-validate",
        filename="smartctl.py",
        substitutes={
            "title": "Storage status",
            "description": "Validate SMART health for all drives in parallel.",
            "timeout": "00:05:00",
        },
    ),
    BuiltinScript(
        name="smartctl-short",
        filename="smartctl.py",
        substitutes={
            "title": "Storage integrity",
            "description": (
                "Run the short SMART self-test and validate SMART health on "
                "all drives in parallel"
            ),
            "timeout": "00:10:00",
        },
    ),
    BuiltinScript(
        name="smartctl-long",
        filename="smartctl.py",
        substitutes={
            "title": "Storage integrity",
            "description": (
                "Run the long SMART self-test and validate SMART health on "
                "all drives in parallel"
            ),
            "timeout": "00:00:00",
        },
    ),
    BuiltinScript(
        name="smartctl-conveyance",
        filename="smartctl.py",
        substitutes={
            "title": "Storage integrity",
            "description": (
                "Run the conveyance SMART self-test and validate SMART health "
                "on all drives in parallel"
            ),
            "timeout": "00:00:00",
        },
    ),
    BuiltinScript(name="memtester", filename="memtester.sh"),
    BuiltinScript(name="stress-ng-cpu-long", filename="stress-ng-cpu-long.sh"),
    BuiltinScript(
        name="stress-ng-cpu-short", filename="stress-ng-cpu-short.sh"
    ),
    BuiltinScript(
        name="stress-ng-memory-long", filename="stress-ng-memory-long.sh"
    ),
    BuiltinScript(
        name="stress-ng-memory-short", filename="stress-ng-memory-short.sh"
    ),
    BuiltinScript(name="ntp", filename="ntp.sh"),
    BuiltinScript(
        name="badblocks",
        filename="badblocks.py",
        substitutes={"description": "Run badblocks on disk in readonly mode."},
    ),
    BuiltinScript(
        name="badblocks-destructive",
        filename="badblocks.py",
        substitutes={
            "description": (
                "Run badblocks on a disk in read/write destructive mode."
            )
        },
    ),
    BuiltinScript(name="7z", filename="seven_z.py"),
    BuiltinScript(name="fio", filename="fio.py"),
    BuiltinScript(
        name="internet-connectivity",
        filename="internet-connectivity.sh",
        inject_file="base-connectivity.sh",
    ),
    BuiltinScript(
        name="gateway-connectivity",
        filename="gateway-connectivity.sh",
        inject_file="base-connectivity.sh",
    ),
    BuiltinScript(
        name="rack-controller-connectivity",
        filename="rack-controller-connectivity.sh",
        inject_file="base-connectivity.sh",
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
            with open(script.inject_path) as f:
                script.substitutes["inject_file"] = f.read()
        script_content = tempita.Template.from_filename(
            script.script_path, encoding="utf-8"
        )
        script_content = script_content.substitute(
            {"name": script.name, **script.substitutes}
        )
        form = None
        try:
            script_in_db = Script.objects.get(name=script.name)
        except Script.DoesNotExist:
            form = ScriptForm(
                data={
                    "script": script_content,
                    "comment": f"Created by maas-{get_maas_version()}",
                }
            )
        else:
            if script_in_db.script.data != script_content:
                # Don't add back old versions of a script. This prevents two
                # connected regions with different versions of a script from
                # fighting with eachother.
                for vtf in script_in_db.script.previous_versions():
                    if vtf.data == script_content:
                        # Don't update anything if we detect we have an old
                        # version of the builtin scripts
                        break
                else:
                    form = ScriptForm(
                        instance=script_in_db,
                        data={
                            "script": script_content,
                            "comment": f"Updated by maas-{get_maas_version()}",
                        },
                        edit_default=True,
                    )

        if form is not None:
            # Form validation should never fail as these are the scripts
            # which ship with MAAS. If they ever do this will be cause by
            # unit tests.
            assert (
                form.is_valid()
            ), f"Builtin script {script.name} caused these errors: {form.errors}"
            script_in_db = form.save(commit=False)
        if NODE_INFO_SCRIPTS.get(script.name, {}).get("run_on_controller"):
            script_in_db.add_tag("deploy-info")
        else:
            script_in_db.remove_tag("deploy-info")
        script_in_db.default = True
        script_in_db.save()

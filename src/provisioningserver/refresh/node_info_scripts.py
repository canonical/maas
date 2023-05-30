# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Builtin node info scripts."""

from collections import OrderedDict
import os

# The name of the script, used throughout MAAS for data processing. Any script
# which is renamed will require a migration otherwise the user will see both
# the old name and new name as two seperate scripts. See
# 0014_rename_dhcp_unconfigured_ifaces.py

# Scripts are run in alpha-numeric order. Scripts which run serially should
# be prefaced with a number(e.g 50-maas-01-). Scripts which run in parallel
# do not need a numeric perface.

# Run first so lldpd can capture data while other scripts run.
LLDP_INSTALL_OUTPUT_NAME = "20-maas-01-install-lldpd"
# Bring up DHCP early so all connected subnets are detected by MAAS.
DHCP_EXPLORE_OUTPUT_NAME = "20-maas-02-dhcp-unconfigured-ifaces"
RUN_MACHINE_RESOURCES = "20-maas-03-machine-resources"
# Run BMC config early as it will enlist new machines.
BMC_DETECTION = "30-maas-01-bmc-config"
# Collect machine configuration hints before commissioning output
MACHINE_CONFIG_HINTS_NAME = "40-maas-01-machine-config-hints"
COMMISSIONING_OUTPUT_NAME = "50-maas-01-commissioning"
# The remaining scripts can run in parallel
SUPPORT_INFO_OUTPUT_NAME = "maas-support-info"
LSHW_OUTPUT_NAME = "maas-lshw"
LIST_MODALIASES_OUTPUT_NAME = "maas-list-modaliases"
GET_FRUID_DATA_OUTPUT_NAME = "maas-get-fruid-api-data"
KERNEL_CMDLINE_OUTPUT_NAME = "maas-kernel-cmdline"
SERIAL_PORTS_OUTPUT_NAME = "maas-serial-ports"
LLDP_OUTPUT_NAME = "maas-capture-lldpd"


def null_hook(node, output, exit_status):
    """Intentionally do nothing.

    Use this to explicitly ignore the response from a built-in
    node info script.
    """


# Built-in node info scripts.  These go into the commissioning tarball
# together with user-provided commissioning scripts or are executed by the
# rack or region refresh process.
#
# The dictionary is keyed on the output filename that the script
# produces. This is so it can be looked up later in the post-processing
# hook.
#
# The contents of each dictionary entry are another dictionary with
# keys:
#   "name" -> the script's name
#   "content" -> the actual script
#   "hook" -> a post-processing hook.
#
# Post-processing hooks can't exist on the rack controller as the rack
# controller isn't running django. On the region controller we set the hooks in
# metadataserver/builtin_scripts/hooks.py
#
# maasserver/status_monitor.py adds 1 minute to the timeout of all scripts for
# cleanup and signaling.
NODE_INFO_SCRIPTS = OrderedDict(
    [
        (
            LLDP_INSTALL_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": False},
        ),
        (
            DHCP_EXPLORE_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": False},
        ),
        (
            BMC_DETECTION,
            {"hook": null_hook, "run_on_controller": False},
        ),
        (
            RUN_MACHINE_RESOURCES,
            {"hook": null_hook, "run_on_controller": True},
        ),
        (
            MACHINE_CONFIG_HINTS_NAME,
            {"hook": null_hook, "run_on_controller": False},
        ),
        (
            COMMISSIONING_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": True},
        ),
        (
            SUPPORT_INFO_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": True},
        ),
        (LSHW_OUTPUT_NAME, {"hook": null_hook, "run_on_controller": True}),
        (
            LIST_MODALIASES_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": True},
        ),
        (
            GET_FRUID_DATA_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": False},
        ),
        (
            KERNEL_CMDLINE_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": False},
        ),
        (
            SERIAL_PORTS_OUTPUT_NAME,
            {"hook": null_hook, "run_on_controller": True},
        ),
        (LLDP_OUTPUT_NAME, {"hook": null_hook, "run_on_controller": False}),
    ]
)


def add_names_to_scripts(scripts):
    """Derive script names from the script output filename.

    Designed for working with the `NODE_INFO_SCRIPTS`
    structure.

    """
    for output_name, config in scripts.items():
        if "name" not in config:
            script_name = os.path.basename(output_name)
            script_name, _ = os.path.splitext(script_name)
            config["name"] = script_name


add_names_to_scripts(NODE_INFO_SCRIPTS)

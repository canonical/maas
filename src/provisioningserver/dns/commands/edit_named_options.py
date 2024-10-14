# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Edit the named.conf.options file so that it includes
the named.conf.options.inside.maas file, which contains the 'forwarders'
setting.
"""


from copy import deepcopy
from datetime import datetime, timezone
import os
import shutil
import sys
from textwrap import dedent

from provisioningserver.dns.config import MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME
from provisioningserver.utils.isc import (
    ISCParseException,
    make_isc_string,
    parse_isc_string,
)


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Edit the named.conf.options file so that it includes the
        named.conf.options.inside.maas file, which contains the 'forwarders'
        and 'dnssec-validation' settings. A backup of the old file will be made
        with the suffix '.maas-YYYY-MM-DDTHH:MM:SS.mmmmmm'.

        This program must be run as root.
        """
    )
    parser.add_argument(
        "--config-path",
        dest="config_path",
        default="/etc/bind/named.conf.options",
        help="Specify the configuration file to edit.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        default=False,
        action="store_true",
        help="Do not edit any configuration; instead, print to stdout the "
        "actions that would be performed, and/or the new "
        "configuration that would be written.",
    )
    parser.add_argument(
        "--force",
        dest="force",
        default=False,
        action="store_true",
        help="Force the BIND configuration to be written, even if it "
        "appears as though nothing has changed.",
    )


def read_file(config_path):
    """Open the named file and return its contents as a string."""
    if not os.path.exists(config_path):
        raise ValueError("%s does not exist" % config_path)

    with open(config_path, encoding="ascii") as fd:
        options_file = fd.read()
    return options_file


def parse_file(config_path, options_file):
    """Read the named.conf.options file and parse it.

    Then insert the include statement that we need.
    """
    try:
        config_dict = parse_isc_string(options_file)
    except ISCParseException as e:
        raise ValueError(f"Failed to parse {config_path}: {str(e)}") from e
    options_block = config_dict.get("options", None)
    if options_block is None:
        # Something is horribly wrong with the file; bail out rather
        # than doing anything drastic.
        raise ValueError(
            "Can't find options {} block in %s, bailing out without "
            "doing anything." % config_path
        )
    return config_dict


def set_up_include_statement(options_block, config_path):
    """Insert the 'include' directive into the parsed options."""
    dir = os.path.join(os.path.dirname(config_path), "maas")
    options_block["include"] = '"{}{}{}"'.format(
        dir,
        os.path.sep,
        MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME,
    )


def back_up_existing_file(config_path):
    now = datetime.now(timezone.utc).isoformat()
    backup_destination = config_path + "." + now
    try:
        shutil.copyfile(config_path, backup_destination)
    except OSError as e:
        raise ValueError(
            "Failed to make a backup of %s, exiting: %s"
            % (config_path, str(e))
        ) from e
    return backup_destination


def write_new_named_conf_options(fd, backup_filename, new_content):
    fd.write(
        """\
//
// This file is managed by MAAS. Although MAAS attempts to preserve changes
// made here, it is possible to create conflicts that MAAS can not resolve.
//
// DNS settings available in MAAS (for example, forwarders and
// dnssec-validation) should be managed only in MAAS.
//
// The previous configuration file was backed up at:
//     %s
//
"""
        % backup_filename
    )
    fd.write(new_content)
    fd.write("\n")


def edit_options(
    config_path,
    stdout=sys.stdout,
    dry_run=False,
    force=False,
    options_handler=None,
):
    """
    Edit the named.conf.options file so that it includes the
    named.conf.options.inside.maas file.
    """
    options_file = read_file(config_path)
    config_dict = parse_file(config_path, options_file)
    original_config = deepcopy(config_dict)

    options_block = config_dict["options"]

    # Modify the configuration (if necessary).
    set_up_include_statement(options_block, config_path)

    # Options handler that can modify the options block more.
    if options_handler is not None:
        options_handler(options_block)

    # Re-parse the new configuration, so we can detect any changes.
    new_content = make_isc_string(config_dict)
    new_config = parse_isc_string(new_content)
    if original_config != new_config or force:
        # The configuration has changed. Back up and write new file.
        if dry_run:
            write_new_named_conf_options(stdout, config_path, new_content)
        else:
            backup_filename = back_up_existing_file(config_path)
            with open(config_path, "w", encoding="ascii") as fd:
                write_new_named_conf_options(fd, backup_filename, new_content)


def run(args, stdout=sys.stdout, stderr=sys.stderr):
    """Call `edit_options`.

    :param args: Parsed output of the arguments added in `add_arguments()`.
    :param stdout: Standard output stream to write to.
    :param stderr: Standard error stream to write to.
    """

    def remove_forwards_dnssec(options_block):
        options_block.pop("forwarders", None)
        options_block.pop("dnssec-validation", None)

    try:
        edit_options(
            args.config_path,
            stdout,
            args.dry_run,
            args.force,
            remove_forwards_dnssec,
        )
    except ValueError as exc:
        stderr.write(str(exc))
        stderr.write("\n")
        stderr.flush()
        return 1

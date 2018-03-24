# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Methods related to initializing a MAAS deployment."""

import argparse
import json
import os
import subprocess


def add_idm_options(parser):
    parser.add_argument(
        '--idm-url', default=None, metavar='IDM_URL',
        help=("The URL to the external IDM server to use for "
              "authentication."))
    parser.add_argument(
        '--idm-user', default=None,
        help="The username to access the IDM server API.")
    parser.add_argument(
        '--idm-key', default=None,
        help="The private key to access the IDM server API.")
    parser.add_argument(
        '--idm-agent-file', type=argparse.FileType('r'),
        help="Agent file containing IDM authentication information")


def add_create_admin_options(parser):
    parser.add_argument(
        '--admin-username', default=None, metavar='USERNAME',
        help="Username for the admin account.")
    parser.add_argument(
        '--admin-password', default=None, metavar='PASSWORD',
        help="Force a given admin password instead of prompting.")
    parser.add_argument(
        '--admin-email', default=None, metavar='EMAIL',
        help="Email address for the admin.")
    parser.add_argument(
        '--admin-ssh-import', default=None, metavar='LP_GH_USERNAME',
        help=(
            "Import SSH keys from Launchpad (lp:user-id) or "
            "Github (gh:user-id) for the admin."))


def create_admin_account(options):
    """Create the first admin account."""
    print_create_header = not all([
        options.admin_username,
        options.admin_password,
        options.admin_email])
    if print_create_header:
        print_msg('Create first admin account:')
    cmd = [get_maas_region_bin_path(), 'createadmin']
    if options.admin_username:
        cmd.extend(['--username', options.admin_username])
    if options.admin_password:
        cmd.extend(['--password', options.admin_password])
    if options.admin_email:
        cmd.extend(['--email', options.admin_email])
    if options.admin_ssh_import:
        cmd.extend(['--ssh-import', options.admin_ssh_import])
    subprocess.call(cmd)


def configure_authentication(options):
    cmd = [get_maas_region_bin_path(), 'configauth']
    if options.idm_url is not None:
        cmd.extend(['--idm-url', options.idm_url])
    if options.idm_user is not None:
        cmd.extend(['--idm-user', options.idm_user])
    if options.idm_key is not None:
        cmd.extend(['--idm-key', options.idm_key])
    if options.idm_agent_file is not None:
        cmd.extend(['--idm-agent-file', options.idm_agent_file.name])
    subprocess.call(cmd)


def get_maas_region_bin_path():
    maas_region = 'maas-region'
    if 'SNAP' in os.environ:
        maas_region = os.path.join(
            os.environ['SNAP'], 'bin', maas_region)
    return maas_region


def get_current_auth_config():
    cmd = [
        get_maas_region_bin_path(),
        'configauth', '--json']
    output = subprocess.check_output(cmd)
    return json.loads(output)


def print_msg(msg='', newline=True):
    """Print a message to stdout.

    Flushes the message to ensure its written immediately.
    """
    print(msg, end=('\n' if newline else ''), flush=True)


def init_maas(options):
        if options.enable_idm:
            print_msg('Configuring authentication')
            configure_authentication(options)
        auth_config = get_current_auth_config()
        skip_create_admin = (
            options.skip_admin or auth_config['external_auth_url'])
        if not skip_create_admin:
            create_admin_account(options)

# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: configure the authentication source."""

__all__ = []

import json

import attr
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.core.validators import URLValidator
from django.db import DEFAULT_DB_ALIAS
from maascli.init import (
    add_candid_options,
    add_rbac_options,
)
from maasserver.management.commands.createadmin import read_input
from maasserver.models import Config


@attr.s
class AuthDetails:

    url = attr.ib(default=None)
    domain = attr.ib(default='')
    user = attr.ib(default='')
    key = attr.ib(default='')
    admin_group = attr.ib(default='')
    rbac_url = attr.ib(default='')


class InvalidURLError(CommandError):
    """User did not provide a valid URL."""


def prompt_for_external_auth_url(existing_url):
    if existing_url == '':
        existing_url = 'none'
    new_url = read_input(
        "URL to external Candid server [default={}]: ".format(existing_url))
    if new_url == '':
        new_url = existing_url
    return new_url


def update_auth_details_from_agent_file(agent_file_name, auth_details):
    """Read a .agent file and return auth details."""
    try:
        with open(agent_file_name) as fh:
            details = json.load(fh)
    except (FileNotFoundError, PermissionError) as error:
        raise CommandError(str(error))
    try:
        agent_details = details.get('agents', []).pop(0)
    except IndexError:
        raise CommandError('No agent users found in agent file')
    # update the passed auth details
    auth_details.url = agent_details.get('url')
    auth_details.user = agent_details.get('username')
    auth_details.key = details.get('key', {}).get('private')


valid_url = URLValidator(schemes=('http', 'https'))


def is_valid_url(auth_url):
    try:
        valid_url(auth_url)
    except ValidationError:
        return False
    return True


def get_auth_config(config_manager):
    config_keys = [
        'external_auth_url', 'external_auth_domain', 'external_auth_user',
        'external_auth_key', 'external_auth_admin_group', 'rbac_url']
    return {key: config_manager.get_config(key) for key in config_keys}


def set_auth_config(config_manager, auth_details):
    config_manager.set_config('external_auth_url', auth_details.url or '')
    config_manager.set_config('external_auth_domain', auth_details.domain)
    config_manager.set_config('external_auth_user', auth_details.user)
    config_manager.set_config('external_auth_key', auth_details.key)
    config_manager.set_config(
        'external_auth_admin_group', auth_details.admin_group)
    config_manager.set_config('rbac_url', auth_details.rbac_url)


def clear_user_sessions():
    Session.objects.all().delete()


class Command(BaseCommand):
    help = "Configure external authentication."

    def add_arguments(self, parser):
        add_candid_options(parser)
        add_rbac_options(parser)
        parser.add_argument(
            '--json', action='store_true', default=False,
            help="Return the current authentication configuration as JSON")

    def handle(self, *args, **options):
        config_manager = Config.objects.db_manager(DEFAULT_DB_ALIAS)

        if options.get('json'):
            print(json.dumps(get_auth_config(config_manager)))
            return

        auth_details = AuthDetails()

        auth_details.rbac_url = _get_or_prompt(
            options, 'rbac_url',
            "URL for the Canonical RBAC service "
            "(leave blank if not using the service): ", replace_none=True)
        if (
                auth_details.rbac_url and
                not is_valid_url(auth_details.rbac_url)):
            raise InvalidURLError(
                "Please enter a valid http or https URL.")

        have_legacy_options = any(
            value is not None for key, value in options.items()
            if key in ('candid_url', 'candid_user', 'candid_key'))
        if have_legacy_options:
            agent_file = options.get('candid_agent_file')
        else:
            agent_file = _get_or_prompt(
                options, 'candid_agent_file',
                'Path of the Candid authentication agent file (leave blank '
                'if not using the service): ', replace_none=True)
            if auth_details.rbac_url and not agent_file:
                raise CommandError(
                    'Candid authentication must be set when using RBAC')
        if agent_file:
            update_auth_details_from_agent_file(agent_file, auth_details)
            if not auth_details.rbac_url:
                auth_details.domain = _get_or_prompt(
                    options, 'candid_domain',
                    "Users domain for external authentication backend "
                    "(leave blank for empty): ", replace_none=True)
                auth_details.admin_group = _get_or_prompt(
                    options, 'candid_admin_group',
                    "Group of users whose members are made admins in MAAS "
                    "(leave blank for empty): ")
        elif have_legacy_options:
            print(
                'Warning: "--idm-*" options are deprecated and will be '
                'removed. Please use "--candid-agent-file" instead to pass '
                'Candid authentication details instead.')
            auth_details.url = options.get('candid_url')
            if auth_details.url is None:
                existing_url = config_manager.get_config('external_auth_url')
                auth_details.url = prompt_for_external_auth_url(existing_url)
            if auth_details.url == 'none':
                auth_details.url = ''
            if auth_details.rbac_url and not auth_details.url:
                raise CommandError(
                    'Candid URL must be specified when using RBAC')
            if auth_details.url:
                if not is_valid_url(auth_details.url):
                    raise InvalidURLError(
                        "Please enter a valid http or https URL.")
                auth_details.user = _get_or_prompt(
                    options, 'candid_user', "Username for Candid API access: ")
                auth_details.key = _get_or_prompt(
                    options, 'candid_key',
                    "Private key for Candid API access: ")
                if not auth_details.rbac_url:
                    auth_details.domain = _get_or_prompt(
                        options, 'candid_domain',
                        "Users domain for external authentication backend "
                        "(leave blank for empty): ", replace_none=True)
                    auth_details.admin_group = _get_or_prompt(
                        options, 'candid_admin_group',
                        "Group of users whose members are made admins in MAAS "
                        "(leave blank for empty): ")

        set_auth_config(config_manager, auth_details)
        clear_user_sessions()


def _get_or_prompt(options, option, message, replace_none=False):
    """Return a config option either from command line or interactive input."""
    config = options.get(option)
    if config is None:
        config = read_input(message)
    if replace_none and config == 'none':
        config = ''
    if config is None:
        config = ''
    return config

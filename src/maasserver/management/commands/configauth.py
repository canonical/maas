# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: configure the authentication source."""

__all__ = []

from django.core.exceptions import ValidationError
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.core.validators import URLValidator
from django.db import DEFAULT_DB_ALIAS
from maasserver.management.commands.createadmin import read_input
from maasserver.models import Config


class InvalidURLError(CommandError):
    """User did not provide a valid URL."""


def prompt_for_external_auth_url(existing_url):
    if existing_url == '':
        existing_url = 'none'
    new_url = read_input(
        "URL to external IDM server [default={}]: ".format(existing_url))
    if new_url == '':
        new_url = existing_url
    return new_url


valid_url = URLValidator(schemes=('http', 'https'))


def is_valid_auth_url(auth_url):
    try:
        valid_url(auth_url)
    except ValidationError:
        return False
    return True


class Command(BaseCommand):
    help = "Configure external authentication."

    def add_arguments(self, parser):
        parser.add_argument(
            '--external-auth-url', default=None,
            help=(
                "The URL to the external IDM server to use for "
                "authentication. Specify '' or 'none' to unset it."))

    def handle(self, *args, **options):
        config_manager = Config.objects.db_manager(DEFAULT_DB_ALIAS)
        auth_url = options.get('external_auth_url', None)
        if auth_url is None:
            existing_url = config_manager.get_config('external_auth_url')
            auth_url = prompt_for_external_auth_url(existing_url)
        if auth_url == 'none':
            auth_url = ''
        if auth_url:
            if not is_valid_auth_url(auth_url):
                raise InvalidURLError(
                    "Please enter a valid http or https URL.")
        config_manager.set_config('external_auth_url', auth_url)

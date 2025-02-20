# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Batch update multiple passwords non-interactively."""

from fileinput import hook_encoded
from fileinput import input as fileinput
from textwrap import dedent

from django.contrib.auth import get_user_model
from django.core.management.base import CommandError

from maasserver.management.commands.base import BaseCommandWithConnection
from maasserver.utils.orm import transactional


class Command(BaseCommandWithConnection):
    help = dedent(
        """\
        Update passwords in batch mode.

        Like the chpasswd command, this command reads a list of username and
        password pairs from standard input and uses this information to update
        a group of existing users. The input must be UTF8 encoded, and each
        line is of the format:

            username:password

        A list of files can be provided as arguments. If provided, the input
        will be read from the files instead of standard input."""
    )

    @transactional
    def handle(self, *args, **options):
        count = 0
        UserModel = get_user_model()
        for line in fileinput(args, openhook=hook_encoded("utf-8")):
            try:
                username, password = line.rstrip("\r\n").split(":", 1)
            except ValueError:
                raise CommandError(  # noqa: B904
                    "Invalid input provided. "
                    "Format is 'username:password', one per line."
                )
            try:
                user = UserModel._default_manager.get(
                    **{UserModel.USERNAME_FIELD: username}
                )
            except UserModel.DoesNotExist:
                raise CommandError("User '%s' does not exist." % username)  # noqa: B904
            user.set_password(password)
            user.save()
            count += 1
        return "%d password(s) successfully changed." % count

# Copyright (c) Django Software Foundation and individual contributors.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     1. Redistributions of source code must retain the above copyright notice,
#        this list of conditions and the following disclaimer.
#
#     2. Redistributions in binary form must reproduce the above copyright
#        notice, this list of conditions and the following disclaimer in the
#        documentation and/or other materials provided with the distribution.
#
#     3. Neither the name of Django nor the names of its contributors may be used
#        to endorse or promote products derived from this software without
#        specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Based on the original file from:
# https://github.com/django/django/blob/65bbdbd10b25700d1166b1a698e672a4695281bc/django/contrib/auth/management/commands/changepassword.py
#
# Slightly modified to defer Django imports until runtime, allowing the command
# to be registered in the parser without requiring Django to be fully loaded. Also, set `requires_migrations_checks` to False
# as the migrations are managed by alembic.

import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, DEFAULT_DB_ALIAS


class Command(BaseCommand):
    help = "Change a MAAS user's password."
    requires_migrations_checks = False
    requires_system_checks = []

    def _get_pass(self, prompt="Password: "):
        p = getpass.getpass(prompt=prompt)
        if not p:
            raise CommandError("aborted")
        return p

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            nargs="?",
            help=(
                "Username to change password for; by default, it's the current "
                "username."
            ),
        )
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            choices=tuple(connections),
            help='Specifies the database to use. Default is "default".',
        )

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        UserModel = get_user_model()

        if options["username"]:
            username = options["username"]
        else:
            username = getpass.getuser()

        try:
            u = UserModel._default_manager.using(options["database"]).get(
                **{UserModel.USERNAME_FIELD: username}
            )
        except UserModel.DoesNotExist as e:
            raise CommandError("user '%s' does not exist" % username) from e

        self.stdout.write("Changing password for user '%s'" % u)

        MAX_TRIES = 3
        count = 0
        p1, p2 = 1, 2  # To make them initially mismatch.
        password_validated = False
        while (p1 != p2 or not password_validated) and count < MAX_TRIES:
            p1 = self._get_pass()
            p2 = self._get_pass("Password (again): ")
            if p1 != p2:
                self.stdout.write("Passwords do not match. Please try again.")
                count += 1
                # Don't validate passwords that don't match.
                continue
            try:
                validate_password(p2, u)
            except ValidationError as err:
                self.stderr.write("\n".join(err.messages))
                count += 1
            else:
                password_validated = True

        if count == MAX_TRIES:
            raise CommandError(
                "Aborting password change for user '%s' after %s attempts"
                % (u, count)
            )

        u.set_password(p1)
        u.save()

        return "Password changed successfully for user '%s'" % u

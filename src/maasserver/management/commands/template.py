# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Update database-backed templates."""

__all__ = []


from optparse import (
    make_option,
    SUPPRESS_HELP,
)
import sys
from textwrap import dedent

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from maasserver.data import templates
from maasserver.models import Template


def _update_templates(verbosity, stdout):
    """Updates each template embedded in the Python code at
    src/maasserver/data/templates.py.
    """
    for filename in sorted(templates):
        data = templates[filename]
        Template.objects.create_or_update_default(
            filename, data, verbosity=verbosity, stdout=stdout)


def _force_delete_all(verbosity, stdout):
    """Forcibly deletes all templates and their corresponding data."""
    if verbosity > 0:
        stdout.write("Deleting %d templates...\n" % Template.objects.count())
    # Need to iterate here so that the custom delete() code gets called.
    for template in Template.objects.all():
        template.delete()
    if verbosity > 0:
        stdout.write("It would now be wise to run:\n")
        stdout.write("    sudo maas-region template update-defaults\n")


class Command(BaseCommand):
    # Note: we don't actually need any options (all of these commands simply
    # look at the `args` list), but Django's command framework will complain
    # if we don't have at least one. So we'll go "above and beyond" and take
    # filenames in argument format, for commands that use them.
    option_list = BaseCommand.option_list + (
        make_option(
            '--filename', dest='filename', default=None, help=SUPPRESS_HELP),
    )
    help = (dedent("""\
        Used to manage MAAS template files.

        Commands:
            list
                Shows a list of all the template files in the database.

            show <filename>
                Displays the current value of the specified template.

            show-default <filename>
                Displays the default value of the specified template.

            update-defaults
                Updates the default value of all templates in the database
                based on the currently-installed MAAS version. (Intended
                to be called automatically during an upgrade or a fresh
                install.)

            force-delete-all
                Forcibly deletes all templates, and associated versioned
                text files stored in the database. Intended to be used in
                the event of a corrupted database.

                IMPORTANT: It would be wise to run the 'update-defaults'
                command immediately after running this, to avoid breaking
                the operation of MAAS.

                VERY IMPORTANT: This will delete any modified templates
                in addition to the templates' default values.
        """))

    def print_error_with_help(self, message, stdout):
        stdout.write(self.help)
        raise CommandError(message)

    def handle(self, *args, **options):
        verbosity = options.get('verbosity')
        filename = options.get('filename')
        stdout = options.get('stdout')
        if stdout is None:
            stdout = sys.stdout
        if len(args) == 0:
            self.print_error_with_help("Command required.", stdout)
        elif args[0] == 'show':
            self._template_show(args, filename, stdout)
        elif args[0] == 'show-default':
            self._template_show_default(args, filename, stdout)
        elif args[0] == 'list':
            self._template_list(args, verbosity, stdout)
        elif args[0] == 'revert':
            self._template_revert(args, filename, verbosity, stdout)
        elif args[0] == 'update-defaults':
            _update_templates(verbosity, stdout)
        elif args[0] == 'force-delete-all':
            _force_delete_all(verbosity, stdout)
        else:
            self.print_error_with_help("Invalid command.", stdout)

    def _template_list(self, args, verbosity, stdout):
        for template in Template.objects.order_by('filename'):
            stdout.write("%s\n" % template.filename)

    def _template_revert(self, args, filename, verbosity, stdout):
        if len(args) > 1:
            filename = args[1]
        template = Template.objects.get_by_filename(filename)
        if template is None:
            raise CommandError("Template not found: %s" % filename)
        template.revert(verbosity=verbosity, stdout=stdout)

    def _template_show_default(self, args, filename, stdout):
        # 'template show-default' command
        if len(args) > 1:
            filename = args[1]
        if filename is None:
            raise CommandError(dedent("""\
                Invalid usage. Required:
                    template show-default <filename>
                """))
        template = Template.objects.get_by_filename(filename)
        if template is not None:
            stdout.write(template.default_value)
        else:
            raise CommandError("Template not found: %s" % filename)

    def _template_show(self, args, filename, stdout):
        # 'template show' command
        if len(args) > 1:
            filename = args[1]
        if filename is None:
            raise CommandError(dedent("""\
                Invalid usage. Required:
                    template show <filename>
                """))
        template = Template.objects.get_by_filename(filename)
        if template is not None:
            stdout.write(template.value)
        else:
            raise CommandError("Template not found: %s" % filename)

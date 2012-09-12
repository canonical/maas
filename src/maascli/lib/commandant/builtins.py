# Commandant is a framework for building command-oriented tools.
# Copyright (C) 2009-2010 Jamshed Kakar.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Builtin commands."""

from cStringIO import StringIO
import os
from platform import platform

import bzrlib
from bzrlib.commands import Command
from bzrlib.option import Option

import commandant
from commandant.help_topics import HelpTopic, CommandHelpTopic
from commandant.formatting import print_columns


class cmd_version(Command):
    """Show version of commandant."""

    takes_options = [Option("short", help="Print just the version number.")]

    def run(self, short=None):
        """Print the version."""
        if short:
            print >>self.outf, "%s" % (self.controller.program_version,)
        else:
            print >>self.outf, "%s %s" % (self.controller.program_name,
                                          self.controller.program_version)
            python_path = os.path.dirname(os.__file__)
            bzrlib_path = bzrlib.__path__[0]
            commandant_path = os.path.abspath(commandant.__path__[0])
            print >>self.outf, "  Platform:", platform(aliased=1)
            print >>self.outf, "  Python standard library:", python_path
            print >>self.outf, "  bzrlib:", bzrlib_path
            print >>self.outf, "  commandant:", commandant_path


class cmd_help(Command):
    """Show help about a command or topic."""

    aliases = ["?", "--help", "-?", "-h"]
    takes_args = ["topic?"]
    _see_also = ["topics"]

    def run(self, topic=None):
        """
        Show help for the C{bzrlib.commands.Command} or L{HelpTopic} matching
        C{name}.

        @param topic: Optionally, the name of the topic to show.  Default is
            C{basic}.
        """
        if topic is None:
            topic = "basic"
        text = None
        command = self.controller.get_command(topic)
        help_topic = self.controller.get_help_topic(topic)
        if help_topic:
            text = help_topic.get_text().strip()
        elif command:
            help_topic = CommandHelpTopic(command)
            help_topic.controller = self.controller
            text = help_topic.get_text()
        if text:
            print >>self.outf, text
        elif not (command or help_topic):
            print >>self.outf, "%s is an unknown command or topic." % (topic,)


class topic_basic(HelpTopic):
    """Show basic help about this program."""

    def get_summary(self):
        """Get a short topic summary for use in a topic listing."""
        return "Basic commands."

    def get_text(self):
        """Get topic content."""
        return """\
%(program-name)s -- %(program-summary)s
%(program-url)s

Basic commands:
  %(program-name)s help commands  List all commands
  %(program-name)s help topics    List all help topics
""" % {"program-name": self.controller.program_name,
       "program-summary": self.controller.program_summary,
       "program-url": self.controller.program_url}


class topic_commands(HelpTopic):
    """List available commands with a short summary describing each one."""

    def get_summary(self):
        """Get a short topic summary for use in a topic listing."""
        return "Basic help for all commands."

    def get_text(self):
        """Get topic content."""
        stream = StringIO()
        result = []
        for name in self.controller.get_command_names():
            command = self.controller.get_command(name)
            help_topic = self.controller.get_help_topic(name)
            if not help_topic and command:
                help_topic = CommandHelpTopic(command)
                if self.controller is not None:
                    help_topic.controller = self.controller
            summary = ""
            if help_topic:
                summary = help_topic.get_summary()
            if self.include_command(command):
                result.append((name, summary))
        result.sort(key=lambda item: item[0])
        print_columns(stream, result)
        return stream.getvalue()

    def include_command(self, command):
        """Return C{True} if C{command} is visible."""
        return not command.hidden


class topic_hidden_commands(topic_commands):
    """List hidden commands with a short summary describing each one."""

    def get_summary(self):
        """Get a short topic summary for use in a topic listing."""
        return "Basic help for hidden commands."

    def include_command(self, command):
        """Return C{True} if C{command} is hidden."""
        return command.hidden


class topic_topics(HelpTopic):
    """List available help topics with a short summary describing each one."""

    def get_summary(self):
        """Get a short topic summary for use in a topic listing."""
        return "Topics list."

    def get_text(self):
        """Get topic content."""
        stream = StringIO()
        command_names = self.controller.get_command_names()
        help_topic_names = self.controller.get_help_topic_names()
        result = [(name, self.controller.get_help_topic(name).get_summary())
                  for name in help_topic_names if name not in command_names]
        result.sort(key=lambda item: item[0])
        print_columns(stream, result)
        return stream.getvalue()

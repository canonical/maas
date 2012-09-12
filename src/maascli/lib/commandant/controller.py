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

"""Infrastructure to run C{bzrlib.commands.Command}s and L{HelpTopic}s."""

import os
import shutil
import stat
import sys
import tempfile

import bzrlib.ui
from bzrlib.commands import run_bzr, Command

from commandant import __version__
from commandant.commands import ExecutableCommand
from commandant.help_topics import FileHelpTopic


DEFAULT_PROGRAM_NAME = "commandant"
DEFAULT_PROGRAM_VERSION = __version__
DEFAULT_PROGRAM_SUMMARY = "A framework for building command-oriented tools."
DEFAULT_PROGRAM_URL = "http://launchpad.net/commandant"


class CommandRegistry(object):

    def __init__(self):
        self._commands = {}

    def install_bzrlib_hooks(self):
        """
        Register this controller with C{Command.hooks} so that the controller
        can take advantage of Bazaar's command infrastructure.  C{bzrlib.ui}
        is initialized for use in a terminal during this process.

        L{_list_commands} and L{_get_command} are registered as callbacks for
        the C{list_commands} and C{get_commands} hooks, respectively.
        """
        Command.hooks.install_named_hook(
            "list_commands", self._list_commands, "commandant commands")
        Command.hooks.install_named_hook(
            "get_command", self._get_command, "commandant commands")
        bzrlib.ui.ui_factory = bzrlib.ui.make_ui_for_terminal(
            sys.stdin, sys.stdout, sys.stderr)

    def _list_commands(self, names):
        """
        Hook to find C{bzrlib.commands.Command} names is called by C{bzrlib}.

        @param names: A set of C{bzrlib.commands.Command} names to update with
            names from this controller.
        """
        names.update(self._commands.iterkeys())
        return names

    def _get_command(self, command, name):
        """
        Hook to get the C{bzrlib.commands.Command} for C{name} is called by
        C{bzrlib}.

        @param command: A C{bzrlib.commands.Command}, or C{None}, to be
            returned if a command matching C{name} can't be found.
        @param name: The name of the C{bzrlib.commands.Command} to retrieve.
        @return: The C{bzrlib.commands.Command} from the index or C{command}
            if one isn't available for C{name}.
        """
        try:
            local_command = self._commands[name]()
        except KeyError:
            return command
        local_command.controller = self
        return local_command

    def register_command(self, name, command_class):
        """Register a C{bzrlib.commands.Command} with this controller.

        @param name: The name to register the command with.
        @param command_class: A type object, typically a subclass of
            C{bzrlib.commands.Command} to use when the command is invoked.
        """
        self._commands[name] = command_class


class HelpTopicRegistry(object):

    def __init__(self):
        self._help_topics = {}

    def register_help_topic(self, name, help_topic_class):
        """Register a C{bzrlib.commands.Command} to this controller.

        @param name: The name to register the command with.
        @param command_class: A type object, typically a subclass of
            C{bzrlib.commands.Command} to use when the command is invoked.
        """
        self._help_topics[name] = help_topic_class

    def get_help_topic_names(self):
        """Get a C{set} of help topic names."""
        return set(self._help_topics.iterkeys())

    def get_help_topic(self, name):
        """
        Get the help topic matching C{name} or C{None} if a match isn't found.
        """
        try:
            help_topic = self._help_topics[name]()
        except KeyError:
            return None
        help_topic.controller = self
        return help_topic


class CommandDiscoveryMixin(object):

    def load_path(self, path):
        """Load C{bzrlib.commands.Command}s and L{HelpTopic}s from C{path}.

        Python files foundin C{path} are loaded and
        C{bzrlib.commands.Command}s and L{HelpTopic}s within are loaded.
        L{ExecutableCommand}s are created for executable programs in C{path}
        and L{FileHelpTopic}s are created for text file help topics.
        """
        package_path = tempfile.mkdtemp()
        try:
            for filename in os.listdir(path):
                file_path = os.path.join(path, filename)
                if filename.endswith("~") or not os.path.exists(file_path):
                    continue
                file_mode = os.stat(file_path)[0]
                if not os.path.isfile(file_path):
                    continue
                if file_mode | stat.S_IEXEC == file_mode:
                    sanitized_name = filename.replace("_", "-")
                    executable = type(
                        "Executable", (ExecutableCommand,),
                        {"path": file_path})
                    self.register_command(sanitized_name, executable)
                elif filename.endswith(".py"):
                    command_module = import_module(filename, file_path,
                                                   package_path)
                    self.load_module(command_module)
                elif filename.endswith(".txt"):
                    sanitized_name = filename.replace("_", "-")[:-4]
                    topic = type(
                        "Topic", (FileHelpTopic,),
                        {"path": file_path})
                    self.register_help_topic(sanitized_name, topic)
        finally:
            shutil.rmtree(package_path)

    def load_module(self, module):
        """Load C{bzrlib.commands.Command}s and L{HelpTopic}s from C{module}.

        Objects found in the module with names that start with C{cmd_} are
        treated as C{bzrlib.commands.Command}s and objects with names that
        start with C{topic_} are treated as L{HelpTopic}s.
        """
        for name in module.__dict__:
            if name.startswith("cmd_"):
                sanitized_name = name[4:].replace("_", "-")
                self.register_command(sanitized_name, module.__dict__[name])
            elif name.startswith("topic_"):
                sanitized_name = name[6:].replace("_", "-")
                self.register_help_topic(sanitized_name, module.__dict__[name])

    def get_command_names(self):
        """
        Get the C{set} of C{bzrlib.commands.Command} names registered with
        this controller.

        This method is equivalent to C{bzrlib.commands.all_command_names} when
        the controller is installed with C{bzrlib}.
        """
        return set(self._commands.iterkeys())

    def get_command(self, name):
        """Get the C{bzrlib.commands.Command} registered for C{name}.

        @return: The C{bzrlib.commands.Command} from the index or C{None} if
            one isn't available for C{name}.
        """
        return self._get_command(None, name)


class CommandExecutionMixin(object):

    def run(self, argv):
        """Run the C{bzrlib.commands.Command} specified in C{argv}.

        @raise BzrCommandError: Raised if a matching command can't be found.
        """
        run_bzr(argv)


class CommandController(CommandRegistry, HelpTopicRegistry,
                        CommandDiscoveryMixin, CommandExecutionMixin):
    """C{bzrlib.commands.Command} discovery and execution controller.

    A L{CommandController} is a container for named C{bzrlib.commands.Command}s
    and L{HelpTopic}s types.  The L{load_module} and L{load_path} methods load
    C{bzrlib.commands.Command} and L{HelpTopic} types from modules and from
    the file system.  The L{register_command} and L{register_help_topic}
    methods register C{bzrlib.commands.Command}s and L{HelpTopic}s types with
    the controller.

    A controller is an execution engine for commands.  The L{run} method
    accepts command line arguments, finds a matching command, and runs it.
    """

    def __init__(self, program_name=None, program_version=None,
                 program_summary=None, program_url=None):
        CommandRegistry.__init__(self)
        HelpTopicRegistry.__init__(self)
        self.program_name = program_name or DEFAULT_PROGRAM_NAME
        self.program_version = program_version or DEFAULT_PROGRAM_VERSION
        self.program_summary = program_summary or DEFAULT_PROGRAM_SUMMARY
        self.program_url = program_url or DEFAULT_PROGRAM_URL


def import_module(filename, file_path, package_path):
    """Import a module and make it a child of C{commandant_command}.

    The module source in C{filename} at C{file_path} is copied to a temporary
    directory, a Python package called C{commandant_command}.

    @param filename: The name of the module file.
    @param file_path: The path to the module file.
    @param package_path: The path for the new C{commandant_command} package.
    @return: The new module.
    """
    module_path = os.path.join(package_path, "commandant_command")
    if not os.path.exists(module_path):
        os.mkdir(module_path)

    init_path = os.path.join(module_path, "__init__.py")
    open(init_path, "w").close()

    source_code = open(file_path, "r").read()
    module_file_path = os.path.join(module_path, filename)
    module_file = open(module_file_path, "w")
    module_file.write(source_code)
    module_file.close()

    name = filename[:-3]
    sys.path.append(package_path)
    try:
        return __import__("commandant_command.%s" % (name,), fromlist=[name])
    finally:
        sys.path.pop()

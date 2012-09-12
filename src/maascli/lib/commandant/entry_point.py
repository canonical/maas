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

"""Bootstrap code starts and runs Commandant."""

from commandant import builtins
from commandant.errors import UsageError
from commandant.controller import CommandController


def main(argv):
    """Run the command named in C{argv}.

    If a command name isn't provided the C{help} command is shown.

    @raises UsageError: Raised if too few arguments are provided.
    @param argv: A list command-line arguments.  The first argument should be
       the path to C{bzrlib.commands.Command}s and L{HelpTopic}s to load and
       the second argument should be the name of the command to run.  Any
       further arguments are passed to the command.
    """
    if len(argv) < 2 or (len(argv) > 1 and argv[1].startswith("-")):
        raise UsageError(
            "You must provide a path to the commands you want to run.")
    elif len(argv) < 3:
        argv.append("help")

    # Load commands topic from the user-supplied path after loading builtins,
    # in case any of the user's commands or topics replace builtin ones.
    controller = CommandController()
    controller.load_module(builtins)
    controller.load_path(argv[1])
    controller.install_bzrlib_hooks()
    controller.run(argv[2:])

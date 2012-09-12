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

"""Infrastructure extends C{bzrlib.commands.Command} to support executables."""

import os
import sys

from twisted.internet.defer import Deferred

from bzrlib.commands import Command


class ExecutableCommand(Command):
    """Specialized command runs an executable program."""

    path = None

    def run_argv_aliases(self, argv, alias_argv=None):
        """
        Disable proper handling of argv and aliases so that arguments can be
        passed directly to the executable.
        """
        self.run(argv)

    def run(self, argv):
        """
        Run the executable, passing whatever arguments were passed to the
        command.
        """
        if argv:
            os.system("%s %s" % (self.path, " ".join(argv)))
        else:
            os.system(self.path)


class TwistedCommand(Command):
    """A command that runs with a Twisted reactor."""

    _return_value = None
    _failure_value = None

    def get_reactor(self):
        """Get the Twisted reactor to use when running this command."""
        from twisted.internet import reactor
        return reactor

    def run_argv_aliases(self, argv, alias_argv=None):
        """Start a reactor for the command to run in."""
        self._start_reactor(argv, alias_argv)
        if self._failure_value is not None:
            type, value, traceback = self._failure_value
            raise type, value, traceback
        return self._return_value

    def _start_reactor(self, argv, alias_argv):
        """Start a reactor and queue a call to run the command."""
        reactor = self.get_reactor()
        reactor.callLater(0, self._run_command, argv, alias_argv)
        reactor.run()
        return self._return_value

    def _run_command(self, argv, alias_argv):
        """Run the command and stop the reactor when it completes."""
        subclass = super(TwistedCommand, self)
        try:
            result = subclass.run_argv_aliases(argv, alias_argv)
        except:
            self._failure_value = sys.exc_info()
            return self._stop_reactor(self._failure_value)
        else:
            return self._stop_reactor(result)

    def _capture_return_value(self, result):
        """Store the return value after running the command."""
        self._return_value = result

    def _capture_failure_value(self, failure):
        """Store the failure value after running the command."""
        self._failure_value = (failure.type, failure.value, failure.tb)

    def _stop_reactor(self, result):
        """Stop the reactor."""
        reactor = self.get_reactor()
        if isinstance(result, Deferred):
            result.addErrback(self._capture_failure_value)
            result.addCallback(self._capture_return_value)
            # Use callLater to stop the reactor so that application code can
            # add callbacks to the Deferred after its been returned by the run
            # method.
            result.addCallback(
                lambda ignored: reactor.callLater(0, reactor.stop))
        else:
            self._capture_return_value(result)
            reactor.callLater(0, reactor.stop)

    def run(self):
        """Actually run the command.

        This method is invoked inside a running Twisted reactor, with the
        options and arguments bound to keyword parameters.

        Return a C{Deferred} or None if the command was successful.  It's okay
        for this method to allow an exception to raise up.
        """
        raise NotImplementedError("Command '%r' needs to be implemented."
                                  % self.name())

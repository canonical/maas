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

"""Infrastructure for building L{HelpTopic} components."""

from inspect import getdoc


class HelpTopic(object):
    """A help topic."""

    controller = None

    def get_summary(self):
        """Get a short topic summary for use in a topic listing."""
        raise NotImplementedError("Must be implemented by sub-class.")

    def get_text(self):
        """Get topic content."""
        raise NotImplementedError("Must be implemented by sub-class.")


class DocstringHelpTopic(object):
    """A help topic that loads content from its docstring."""

    def __init__(self):
        super(DocstringHelpTopic, self).__init__()
        self._summary = None
        self._text = None

    def _get_docstring(self):
        """Get the docstring for this help topic."""
        return getdoc(self)

    def _load_help_text(self):
        """Load summary and text content."""
        docstring = self._get_docstring()
        if not docstring:
            return "", ""
        else:
            return self._load_docstring(docstring)

    def _load_docstring(self, docstring):
        """Load summary and text content from a docstring."""
        lines = [line for line in docstring.splitlines()]
        return lines[0], "\n".join(lines[1:]).strip()

    def get_summary(self):
        """Get a short topic summary for use in a topic listing."""
        if self._summary is None:
            (self._summary, self._text) = self._load_help_text()
        return self._summary

    def get_text(self):
        """Get topic content."""
        if self._text is None:
            (self._summary, self._text) = self._load_help_text()
        return self._text


class FileHelpTopic(HelpTopic):
    """A help topic that loads content from a file."""

    path = None

    def __init__(self):
        super(FileHelpTopic, self).__init__()
        self._summary = None
        self._text = None

    def _load(self):
        """Load and cache summary and text content."""
        file = open(self.path, "r")
        self._summary = file.readline().strip()
        self._text = file.read().strip()
        # FIXME Test this.
        file.close()

    def get_summary(self):
        """Get a short topic summary for use in a topic listing."""
        if self._summary is None:
            self._load()
        return self._summary

    def get_text(self):
        """Get topic content."""
        if self._text is None:
            self._load()
        return self._text


class CommandHelpTopic(DocstringHelpTopic):
    """
    A help topic that loads content from a C{bzrlib.commands.Command}
    docstring.
    """

    def __init__(self, command):
        super(CommandHelpTopic, self).__init__()
        self.command = command

    def _get_docstring(self):
        """Get the docstring for the command."""
        return getdoc(self.command)

    def _load_docstring(self, docstring):
        """Load summary and text content from a docstring."""
        lines = [line for line in docstring.splitlines()]
        summary = lines[0]
        try:
            text = self.command.get_help_text().strip()
            text = text.replace("bzr", self.controller.program_name)
        except NotImplementedError:
            pass
        else:
            return summary, text
        return summary, ""

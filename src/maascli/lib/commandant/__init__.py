"""Commandant is a framework for building command-oriented tools.

A command-oriented command-line program takes a command name as its first
argument, which it finds and runs, passing along any subsequent
arguments.  Bazaar is command-oriented, for instance.  Commandant is inspired
by Bazaar's user interface and uses bzrlib in its internal implementation.

Commandant is a command discovery and execution tool.  Executables, such as
shell scripts, can be used as commands.  Commands can also be implemented in
Python.  These commands, along with help topics, are bundled together in a
directory.  Commandant, when pointed at the directory containing the commands,
provides a Bazaar-like user interface to discover and run them.
"""

__version__ = "0.4.0"
__version_info__ = (0, 4, 0)

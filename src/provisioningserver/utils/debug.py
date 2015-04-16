# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for debugging."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'get_full_thread_dump',
    'print_full_thread_dump',
    'register_sigusr2_thread_dump_handler',
    ]

import cStringIO
import signal
from sys import _current_frames as current_frames
import threading
from time import (
    gmtime,
    strftime,
)
import traceback


def get_full_thread_dump():
    """Returns a string containing a traceback for all threads"""
    output = cStringIO.StringIO()
    time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    thread_names = {}
    for thread in threading.enumerate():
        thread_names[thread.ident] = thread.name
    output.write("\n>>>> Begin stack trace (%s) >>>>\n" % time)
    for threadId, stack in current_frames().items():
        output.write(
            "\n# ThreadID: %s (%s)\n" %
            (threadId, thread_names.get(threadId, "unknown")))
        for filename, lineno, name, line in traceback.extract_stack(stack):
            output.write(
                'File: "%s", line %d, in %s\n' %
                (filename, lineno, name))
            if line:
                output.write("  %s\n" % (line.strip()))
    output.write("\n<<<< End stack trace <<<<\n\n")

    thread_dump = output.getvalue()
    output.close()
    return thread_dump


def print_full_thread_dump(signum=None, stack=None):
    """Creates a full thread dump, then prints it to stdout."""
    print(get_full_thread_dump())


def register_sigusr2_thread_dump_handler():
    """Installs a signal handler which will print a full thread dump
    upon receiving SIGUSR2."""
    # installing a signal handler only works from the main thread.
    # some of our test cases may run this from something that isn't
    # the main thread, however...
    if threading.current_thread().__class__.__name__ == '_MainThread':
        signal.signal(signal.SIGUSR2, print_full_thread_dump)

# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for debugging."""

import cProfile
from datetime import datetime, timezone
import functools
import io
import os
import signal
from sys import _current_frames as current_frames
import threading
from time import gmtime, strftime
import traceback

from provisioningserver.path import get_maas_data_path

_profile = None


def toggle_cprofile(process_name, signum=None, stack=None):
    """Toggle cProfile profiling of the process.

    If it's called when no profiling is enabled, profiling will start.

    If it's called when profiling is enabled, profiling is stopped and
    the stats are written to $MAAS_DATA/profiling, with the
    process name and pid in the name.
    """
    global _profile
    if _profile is None:
        _profile = cProfile.Profile()
        _profile.enable()
        print("Profiling enabled")
    else:
        current_time = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )
        profiling_dir = get_maas_data_path("profiling")
        os.makedirs(profiling_dir, exist_ok=True)
        output_filename = f"{process_name}-{os.getpid()}-{current_time}.pyprof"
        full_filepath = os.path.join(profiling_dir, output_filename)
        _profile.create_stats()
        _profile.dump_stats(full_filepath)
        _profile = None
        print(f"Profiling disabled. Output written to {full_filepath}")


def get_full_thread_dump():
    """Returns a string containing a traceback for all threads"""
    output = io.StringIO()
    time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
    thread_names = {}
    for thread in threading.enumerate():
        thread_names[thread.ident] = thread.name
    output.write("\n>>>> Begin stack trace (%s) >>>>\n" % time)
    for threadId, stack in current_frames().items():
        output.write(
            "\n# ThreadID: %s (%s)\n"
            % (threadId, thread_names.get(threadId, "unknown"))
        )
        for filename, lineno, name, line in traceback.extract_stack(stack):
            output.write(
                'File: "%s", line %d, in %s\n' % (filename, lineno, name)
            )
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
    if threading.current_thread().__class__.__name__ == "_MainThread":
        signal.signal(signal.SIGUSR2, print_full_thread_dump)


def register_sigusr1_toggle_cprofile(process_name):
    """Toggle cProfile profiling upon receiving SIGUSR1."""
    # installing a signal handler only works from the main thread.
    # some of our test cases may run this from something that isn't
    # the main thread, however...
    toggle_process_cprofile = functools.partial(toggle_cprofile, process_name)
    if threading.current_thread().__class__.__name__ == "_MainThread":
        signal.signal(signal.SIGUSR1, toggle_process_cprofile)

# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for inspecting processes."""

from functools import lru_cache
import os

from provisioningserver.utils.fs import read_text_file
from provisioningserver.utils.shell import call_and_check, ExternalProcessError


def is_pid_running(pid):
    """Return True if the `pid` is running."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    else:
        return True


def is_pid_in_container(pid, proc_path="/proc"):
    """Return True if the `pid` is running in a container.

    This should only be called when not running in a container itself, because
    if this process is running in a container than the `pid` process is
    sure to be running in the container as well.
    """
    cgroup_path = os.path.join(proc_path, str(pid), "cgroup")
    cgroup_info = read_text_file(cgroup_path)
    for line in cgroup_info.splitlines():
        id_num, subsytem, hierarchy = line.split(":", 2)
        if hierarchy.startswith("/lxc") or "docker" in hierarchy:
            return True
    return False


@lru_cache(maxsize=1)
def running_in_container():
    """Return True if running in an LXC or Docker container."""
    try:
        call_and_check(["systemd-detect-virt", "-c"])
    except ExternalProcessError:
        # Exited non-zero so not in a container.
        return False
    else:
        # Exited zero so inside a container.
        return True


def get_running_pids_with_command(
    command, exclude_container_processes=True, proc_path="/proc"
):
    """Return list of pids that are running the following command.

    :param command: The command to search for. This is only the command as
        `cat` not the full command line.
    :param exclude_container_processes: Excludes processes that are running
        in an LXC container on the host.
    """
    running_pids = [pid for pid in os.listdir(proc_path) if pid.isdigit()]
    pids = []
    for pid in running_pids:
        try:
            pid_command = read_text_file(
                os.path.join(proc_path, pid, "comm")
            ).strip()
        except (FileNotFoundError, ProcessLookupError):
            # Process was closed while running.
            pass
        else:
            if pid_command == command:
                pids.append(int(pid))

    if exclude_container_processes and not running_in_container():
        return [
            pid
            for pid in pids
            if not is_pid_in_container(pid, proc_path=proc_path)
        ]
    else:
        return pids

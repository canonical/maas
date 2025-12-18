# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Figure out server address for the maas_url setting."""

from subprocess import check_output

from provisioningserver.utils.shell import get_env_with_locale

# fcntl operation as defined in <ioctls.h>.  This is GNU/Linux-specific!
SIOCGIFADDR = 0x8915


def get_command_output(*command_line):
    """Execute a command line, and return its output.

    Raises an exception if return value is nonzero.

    :param *command_line: Words for the command line.  No shell expansions
        are performed.
    :type *command_line: Sequence of unicode.
    :return: Output from the command.
    :rtype: List of unicode, one per line.
    """
    env = get_env_with_locale()
    output = check_output(command_line, env=env)
    return output.decode("utf-8").splitlines()

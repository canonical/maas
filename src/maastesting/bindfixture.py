# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Server fixture for BIND."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'BINDServer',
    ]

import argparse
import os
from shutil import copy
import subprocess
from textwrap import dedent
import time

import fixtures
from provisioningserver.dns.config import generate_rndc
from provisioningserver.utils import atomic_write
from rabbitfixture.server import (
    allocate_ports,
    preexec_fn,
    )
import tempita
from testtools.content import Content
from testtools.content_type import UTF8_TEXT


def should_write(path, overwrite_config=False):
    """Does the DNS config file at `path` need writing?

    :param path: File that may need to be written out.
    :param overwrite_config: Overwrite config files even if they
        already exist?
    :return: Whether the file should be written.
    :rtype: bool
    """
    return overwrite_config or not os.path.exists(path)


class BINDServerResources(fixtures.Fixture):
    """Allocate the resources a BIND server needs.

    :ivar port: A port that was free at the time setUp() was
        called.
    :ivar rndc_port: A port that was free at the time setUp() was
        called (used for rndc communication).
    :ivar homedir: A directory where to put all the files the
        BIND server needs (configuration files and executable).
    :ivar log_file: The log file allocated for the server.
    """

    # The full path where the 'named' executable can be
    # found.
    # Note that it will be copied over to a temporary
    # location in order to by-pass the limitations imposed by
    # apparmor if the executable is in /usr/sbin/named.
    NAMED_PATH = '/usr/sbin/named'

    # The configuration template for the BIND server.  The goal here
    # is to override the defaults (default configuration files location,
    # default port) to avoid clashing with the system's BIND (if
    # running).
    NAMED_CONF_TEMPLATE = tempita.Template(dedent("""
      options {
        directory "{{homedir}}";
        listen-on port {{port}} {127.0.0.1;};
        pid-file "{{homedir}}/named.pid";
        session-keyfile "{{homedir}}/session.key";
      };

      logging{
        channel simple_log {
          file "{{log_file}}";
          severity info;
          print-severity yes;
        };
        category default{
          simple_log;
        };
      };

      {{extra}}
    """))

    def __init__(self, port=None, rndc_port=None, homedir=None,
                 log_file=None):
        super(BINDServerResources, self).__init__()
        self._defaults = dict(
            port=port,
            rndc_port=rndc_port,
            homedir=homedir,
            log_file=log_file,
            )

    def setUp(self, overwrite_config=False):
        super(BINDServerResources, self).setUp()
        self.__dict__.update(self._defaults)
        self.set_up_config()
        self.set_up_named(overwrite_config=overwrite_config)

    def set_up_named(self, overwrite_config=True):
        """Setup an environment to run 'named'.

        - Create the default configuration for 'named' and setup rndc.
        - Copies the 'named' executable inside homedir (to by-pass the
        restrictions that apparmor imposes
        """
        # Generate rndc configuration (rndc config and named snippet).
        rndcconf, namedrndcconf = generate_rndc(
            self.rndc_port, 'dnsfixture-rndc-key')
        # Write main BIND config file.
        if should_write(self.conf_file, overwrite_config):
            named_conf = (
                self.NAMED_CONF_TEMPLATE.substitute(
                    homedir=self.homedir, port=self.port,
                    log_file=self.log_file,
                    extra=namedrndcconf))
            atomic_write(named_conf, self.conf_file)
        # Write rndc config file.
        if should_write(self.rndcconf_file, overwrite_config):
            atomic_write(rndcconf, self.rndcconf_file)

        # Copy named executable to home dir.  This is done to avoid
        # the limitations imposed by apparmor if the executable
        # is in /usr/sbin/named.
        # named's apparmor profile prevents loading of zone and
        # configuration files from outside of a restricted set,
        # none of which an ordinary user has write access to.
        if should_write(self.named_file, overwrite_config):
            named_path = self.NAMED_PATH
            assert os.path.exists(named_path), (
                "'%s' executable not found.  Install the package "
                "'bind9' or define an environment variable named "
                "NAMED_PATH with the path where the 'named' "
                "executable can be found." % named_path)
            copy(named_path, self.named_file)

    def set_up_config(self):
        if self.port is None:
            [self.port] = allocate_ports(1)
        if self.rndc_port is None:
            [self.rndc_port] = allocate_ports(1)
        if self.homedir is None:
            self.homedir = self.useFixture(fixtures.TempDir()).path
        if self.log_file is None:
            self.log_file = os.path.join(self.homedir, 'named.log')
        self.named_file = os.path.join(
            self.homedir, os.path.basename(self.NAMED_PATH))
        self.conf_file = os.path.join(self.homedir, 'named.conf')
        self.rndcconf_file = os.path.join(self.homedir, 'rndc.conf')


class BINDServerRunner(fixtures.Fixture):
    """Run a BIND server."""

    # Where the executable 'rndc' can be found (belongs to the
    # package 'bind9utils').
    RNDC_PATH = "/usr/sbin/rndc"

    def __init__(self, config):
        """Create a `BINDServerRunner` instance.

        :param config: An object exporting the variables
            `BINDServerResources` exports.
        """
        super(BINDServerRunner, self).__init__()
        self.config = config
        self.process = None

    def setUp(self):
        super(BINDServerRunner, self).setUp()
        self._start()

    def is_running(self):
        """Is the BIND server process still running?"""
        if self.process is None:
            return False
        else:
            return self.process.poll() is None

    def _spawn(self):
        """Spawn the BIND server process."""
        env = dict(os.environ, HOME=self.config.homedir)
        with open(self.config.log_file, "wb") as log_file:
            with open(os.devnull, "rb") as devnull:
                self.process = subprocess.Popen(
                    [self.config.named_file, "-f", "-c",
                     self.config.conf_file],
                    stdin=devnull,
                    stdout=log_file, stderr=log_file,
                    close_fds=True, cwd=self.config.homedir,
                    env=env, preexec_fn=preexec_fn)
        # Keep the log_file open for reading so that we can still get the log
        # even if the log is deleted.
        open_log_file = open(self.config.log_file, "rb")
        self.addDetail(
            os.path.basename(self.config.log_file),
            Content(UTF8_TEXT, lambda: open_log_file))

    def rndc(self, command):
        """Executes a ``rndc`` command and returns status."""
        if isinstance(command, basestring):
            command = (command,)
        ctl = subprocess.Popen(
            (self.RNDC_PATH, "-c", self.config.rndcconf_file) +
                command,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=preexec_fn)
        outstr, errstr = ctl.communicate()
        return outstr, errstr

    def is_server_running(self):
        """Checks that the BIND server is up and running."""
        outdata, errdata = self.rndc("status")
        return "server is up and running" in outdata

    def _start(self):
        """Start the BIND server."""
        self._spawn()
        # Wait for the server to come up: stop when the process is dead, or
        # the timeout expires, or the server responds.
        timeout = time.time() + 15
        while time.time() < timeout and self.is_running():
            if self.is_server_running():
                break
            time.sleep(0.3)
        else:
            raise Exception(
                "Timeout waiting for BIND server to start: log in %r." %
                (self.config.log_file,))
        self.addCleanup(self._stop)

    def _request_stop(self):
        outstr, errstr = self.rndc("stop")
        if outstr:
            self.addDetail('stop-out', Content(UTF8_TEXT, lambda: [outstr]))
        if errstr:
            self.addDetail('stop-err', Content(UTF8_TEXT, lambda: [errstr]))

    def _stop(self):
        """Stop the running server. Normally called by cleanups."""
        self._request_stop()
        # Wait for the server to go down...
        timeout = time.time() + 15
        while time.time() < timeout:
            if not self.is_server_running():
                break
            time.sleep(0.3)
        else:
            raise Exception(
                "Timeout waiting for BIND server to go down.")


class BINDServer(fixtures.Fixture):
    """A BIND server fixture.

    When setup a BIND instance will be running.

    :ivar config: The `BINDServerResources` used to start the server.
    """

    def __init__(self, config=None):
        super(BINDServer, self).__init__()
        self.config = config

    def setUp(self):
        super(BINDServer, self).setUp()
        if self.config is None:
            self.config = BINDServerResources()
        self.useFixture(self.config)
        self.runner = BINDServerRunner(self.config)
        self.useFixture(self.runner)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run a BIND server.')
    parser.add_argument(
        '--homedir',
        help=(
            "A directory where to put all the files the BIND"
            "server needs (configuration files and executable)"
           ))
    parser.add_argument(
        '--log-file',
        help="The log file allocated for the server")
    parser.add_argument(
        '--port', type=int,
        help="The port that will be used by BIND")
    parser.add_argument(
        '--rndc-port', type=int,
        help="The rndc port that will be used by BIND")
    parser.add_argument(
        '--overwrite_config', type=bool,
        help="Whether or not to overwrite the configuration files "
             "if they already exist", default=False)
    arguments = parser.parse_args()

    # Create homedir if it does not already exist.
    try:
        os.makedirs(arguments.homedir)
    except OSError:
        pass
    # Create BINDServerResources with the provided options.
    resources = BINDServerResources(
        homedir=arguments.homedir, log_file=arguments.log_file,
        port=arguments.port, rndc_port=arguments.rndc_port)
    resources.setUp(overwrite_config=arguments.overwrite_config)
    # exec named.
    os.execlp(
        resources.named_file, resources.named_file, "-g", "-c",
        resources.conf_file)

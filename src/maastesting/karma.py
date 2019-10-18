# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper to start the Karma environment to run MAAS JS unit-tests."""

__all__ = [
    ]

import argparse
import os
from subprocess import Popen

from maastesting.fixtures import DisplayFixture


def run_karma():
    """Start Karma with the MAAS JS testing configuration."""
    browsers = {"PhantomJS": {}}

    parser = argparse.ArgumentParser(
        description='Run javascript tests with karma')
    parser.add_argument(
        '--browsers', nargs='*', help='browser(s) to run tests with',
        choices=browsers, default=list(browsers))
    args = parser.parse_args()

    def run_with_browser(browser, env):
        """Run tests with a specific browser and environment."""
        command = (
            'include/nodejs/bin/node', 'bin/karma', 'start', '--single-run',
            '--no-colors', '--browsers', browser,
            'src/maastesting/karma.conf.js')
        karma = Popen(command, env=dict(os.environ, **env))
        return karma.wait()

    with DisplayFixture():
        for browser in args.browsers:
            # run karma separately for each browser, since running multiple
            # browsers seems to tringger a buggy behavior in karma which makes
            # some tests fail with page reload (lp:1762344)
            ret = run_with_browser(browser, env=browsers[browser])
            if ret:
                raise SystemExit(ret)

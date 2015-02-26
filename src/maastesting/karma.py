# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper to start the Karma environment to run MAAS JS unit-tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]

from subprocess import (
    CalledProcessError,
    check_output,
    Popen,
    )

from maastesting.fixtures import DisplayFixture


BROWSERS = (
    ('Chrome', 'google-chrome'),
    ('Firefox', 'firefox'),
    ('Opera', 'opera'),
    )


def is_browser_available(browser):
    """Return True if browser is available."""
    try:
        check_output(('which', browser))
    except CalledProcessError:
        return False
    return True


def get_available_list_of_browsers():
    """Get list of available browsers for the current system."""
    # PhantomJS is always enabled.
    browsers = ['PhantomJS']

    # Build list of browsers to enable.
    for name, path in BROWSERS:
        if is_browser_available(path):
            browsers.append(name)
    return browsers


def run_karma():
    """Start Karma with the MAAS JS testing configuration."""
    with DisplayFixture():
        karma = Popen((
            'bin/karma', 'start',
            '--single-run',
            '--no-colors',
            '--browsers', ','.join(get_available_list_of_browsers()),
            'src/maastesting/karma.conf.js',
        ))
        raise SystemExit(karma.wait())

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

import os
from subprocess import (
    CalledProcessError,
    check_output,
    Popen,
    )

from maastesting.fixtures import DisplayFixture


def is_browser_available(browser):
    """Return True if browser is available."""
    try:
        check_output(('which', browser))
    except CalledProcessError:
        return False
    else:
        return True


def gen_available_browsers():
    """Find available browsers for the current system.

    Yields ``(name, environ)`` tuples, where ``name`` is passed to the runner,
    and ``environ`` is a dict of additional environment variables needed to
    run the given browser.
    """
    # PhantomJS is always enabled.
    yield "PhantomJS", {}

    if is_browser_available("firefox"):
        yield "Firefox", {}

    # Prefer Chrome, but fall-back to Chromium.
    if is_browser_available("google-chrome"):
        yield "Chrome", {"CHROME_BIN": "google-chrome"}
    elif is_browser_available("chromium-browser"):
        yield "Chrome", {"CHROME_BIN": "chromium-browser"}

    if is_browser_available("opera"):
        yield "Opera", {}


def run_karma():
    """Start Karma with the MAAS JS testing configuration."""
    browsers = set()  # Names passed to bin/karma.
    extra = {}  # Additional environment variables.

    for name, env in gen_available_browsers():
        browsers.add(name)
        extra.update(env)

    command = (
        'bin/karma', 'start', '--single-run', '--no-colors', '--browsers',
        ','.join(browsers), 'src/maastesting/karma.conf.js')

    with DisplayFixture():
        karma = Popen(command, env=dict(os.environ, **extra))
        raise SystemExit(karma.wait())

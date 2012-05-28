# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Run YUI3 unit tests with SST (http://testutils.org/sst/)."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from abc import (
    ABCMeta,
    abstractmethod,
    )
from glob import glob
import json
import os
from os.path import abspath
from urlparse import urljoin

from maastesting import yui3
from maastesting.fixtures import (
    DisplayFixture,
    SSTFixture,
    )
from maastesting.httpd import HTTPServerFixture
from maastesting.testcase import TestCase
from maastesting.utils import extract_word_list
from nose.tools import nottest
from saucelabsfixture import (
    SauceConnectFixture,
    SSTOnDemandFixture,
    )
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from sst.actions import (
    assert_text,
    get_element,
    go_to,
    wait_for,
    )
from testtools import clone_test_with_new_id

# Nose is over-zealous.
nottest(clone_test_with_new_id)


def get_browser_names_from_env():
    """Parse the environment variable ``MAAS_TEST_BROWSERS`` to get a list of
    the browsers to use for the JavaScript tests.

    Returns ['Firefox'] if the environment variable is not present.
    """
    names = os.environ.get('MAAS_TEST_BROWSERS', 'Firefox')
    return extract_word_list(names)


# See <https://saucelabs.com/docs/ondemand/browsers/env/python/se2/linux> for
# more information on browser/platform choices.
remote_browsers = {
    "ie7": dict(
        DesiredCapabilities.INTERNETEXPLORER,
        version="7", platform="XP"),
    "ie8": dict(
        DesiredCapabilities.INTERNETEXPLORER,
        version="8", platform="XP"),
    "ie9": dict(
        DesiredCapabilities.INTERNETEXPLORER,
        version="9", platform="VISTA"),
    "chrome": dict(
        DesiredCapabilities.CHROME,
        platform="VISTA"),
    }


def get_remote_browser_names_from_env():
    """Parse the environment variable ``MAAS_REMOTE_TEST_BROWSERS`` to get a
    list of the browsers to use for the JavaScript tests.

    Returns [] if the environment variable is not present.
    """
    names = os.environ.get('MAAS_REMOTE_TEST_BROWSERS', '')
    names = [name.lower() for name in extract_word_list(names)]
    unrecognised = set(names).difference(remote_browsers)
    if len(unrecognised) > 0:
        raise ValueError("Unrecognised browsers: %r" % unrecognised)
    return names


class YUIUnitTestsBase:
    """Base class for running YUI3 tests in a variety of browsers.

    Calls to instance of this class are intercepted. If the call is to a clone
    the superclass is called, and thus the test executes as normal. Otherwise
    the `multiply` method is called. This method can then arrange for the
    testcase to be run in multiple environments, cloning the test for each.

    In this way it can efficiently set-up and tear-down resources for the
    tests, and also report on a per-test basis. If test resources were fully
    working for MAAS tests this might not be necessary, but at the time of
    implementation this was a solution with the lowest friction (at least,
    lower than ripping nose out, or teaching it about test resources).
    """

    __metaclass__ = ABCMeta

    test_paths = glob("src/maasserver/static/js/tests/*.html")
    assert test_paths != [], "No JavaScript unit test pages found."

    # Indicates if this test has been cloned.
    cloned = False

    def clone(self, suffix):
        # Clone this test with a new suffix.
        test = clone_test_with_new_id(
            self, "%s#%s" % (self.id(), suffix))
        test.cloned = True
        return test

    @abstractmethod
    def multiply(self, result):
        """Run the test for each of a specified range of browsers.

        This method should sort out shared fixtures.
        """

    def __call__(self, result=None):
        if self.cloned:
            # This test has been cloned; just call-up to run the test.
            super(YUIUnitTestsBase, self).__call__(result)
        else:
            self.multiply(result)

    def test_YUI3_unit_tests(self):
        # Load the page and then wait for #suite to contain
        # 'done'.  Read the results in '#test_results'.
        go_to(self.test_url)
        wait_for(assert_text, 'suite', 'done')
        results = json.loads(get_element(id='test_results').text)
        if results['failed'] != 0:
            message = '%d test(s) failed.\n\n%s' % (
                results['failed'], yui3.get_failed_tests_message(results))
            self.fail(message)


class YUIUnitTestsLocal(YUIUnitTestsBase, TestCase):

    scenarios = tuple(
        (path, {"test_url": "file://%s" % abspath(path)})
        for path in YUIUnitTestsBase.test_paths)

    def multiply(self, result):
        # Run this test locally for each browser requested. Use the same
        # display fixture for all browsers. This is done here so that all
        # scenarios are played out for each browser in turn; starting and
        # stopping browsers is costly.
        with DisplayFixture():
            for browser_name in get_browser_names_from_env():
                browser_test = self.clone("local:%s" % browser_name)
                with SSTFixture(browser_name):
                    browser_test(result)


class YUIUnitTestsRemote(YUIUnitTestsBase, TestCase):

    def multiply(self, result):
        # Now run this test remotely for each requested Sauce OnDemand
        # browser requested.
        browser_names = get_remote_browser_names_from_env()
        if len(browser_names) == 0:
            return

        # A web server is needed so the OnDemand service can obtain local
        # tests. Be careful when choosing web server ports; only a scattering
        # are proxied. See <https://saucelabs.com/docs/ondemand/connect>.
        with HTTPServerFixture(port=5555) as httpd:
            scenarios = tuple(
                (path, {"test_url": urljoin(httpd.url, path)})
                for path in self.test_paths)
            with SauceConnectFixture() as sauce_connect:
                for browser_name in browser_names:
                    capabilities = remote_browsers[browser_name]
                    sst_ondemand = SSTOnDemandFixture(
                        capabilities, sauce_connect.control_url)
                    with sst_ondemand:
                        browser_test = self.clone("remote:%s" % browser_name)
                        browser_test.scenarios = scenarios
                        browser_test(result)

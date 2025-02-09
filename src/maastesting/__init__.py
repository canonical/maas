# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing infrastructure for MAAS."""

import copy
from os import environ
from os.path import abspath, dirname, join, pardir, realpath
import re
from unittest import mock
from warnings import filterwarnings


def get_testing_timeout(timeout=None):
    wait_time = (
        environ.get("MAAS_WAIT_FOR_REACTOR", 120.0)
        if timeout is None
        else timeout
    )
    return float(wait_time)


# get_testing_timeout is a test helper, not a test. This tells nose that it shouldn't be collected.
# See https://nose.readthedocs.io/en/latest/finding_tests.html
get_testing_timeout.__test__ = False

# The root of the source tree.
dev_root = abspath(join(dirname(realpath(__file__)), pardir, pardir))

# The bin/ directory in the source tree.
bindir = join(dev_root, "bin")

# Construct a regular expression that matches all of MAAS's core
# packages, and their subpackages.
packages = {
    "apiclient",
    "maas",
    "maascli",
    "maasserver",
    "maastesting",
    "metadataserver",
    "provisioningserver",
}
packages_expr = r"^(?:%s)\b" % "|".join(
    re.escape(package) for package in packages
)

# Enable some warnings that we ought to pay heed to.
filterwarnings("error", category=BytesWarning, module=packages_expr)
filterwarnings("default", category=DeprecationWarning, module=packages_expr)
filterwarnings("default", category=ImportWarning, module=packages_expr)

# Ignore noisy deprecation warnings inside Twisted.
filterwarnings("ignore", category=DeprecationWarning, module=r"^twisted\b")

# Make sure that sentinel objects are not copied.
sentinel_type = type(mock.sentinel.foo)
copy._copy_dispatch[sentinel_type] = copy._copy_immutable
copy._deepcopy_dispatch[sentinel_type] = copy._copy_immutable


# This patches testtools.content.TracebackContent to fix LP:1188420
# and remove if False crud

import traceback  # noqa: E402

import testtools.content  # noqa: E402


class MAASTracebackContent(testtools.content.Content):
    """Content object for tracebacks.

    This adapts an exc_info tuple to the 'Content' interface.
    'text/x-traceback;language=python' is used for the mime type, in order to
    provide room for other languages to format their tracebacks differently.
    """

    def __init__(self, err, test, capture_locals=False):
        """Create a TracebackContent for ``err``.

        :param err: An exc_info error tuple.
        :param test: A test object used to obtain failureException.
        :param capture_locals: If true, show locals in the traceback.
        """
        if err is None:
            raise ValueError("err may not be None")

        exctype, value, tb = err
        # Skip test runner traceback levels
        if testtools.content.StackLinesContent.HIDE_INTERNAL_STACK:
            while tb and "__unittest" in tb.tb_frame.f_globals:
                tb = tb.tb_next

        limit = None
        if (
            testtools.content.StackLinesContent.HIDE_INTERNAL_STACK
            and test.failureException
            and isinstance(value, test.failureException)
        ):
            # Skip assert*() traceback levels
            limit = 0
            for frame, line_no in traceback.walk_tb(tb):  # noqa: B007
                if "__unittest" in frame.f_globals:
                    break
                limit += 1

        stack_lines = list(
            traceback.TracebackException(
                exctype, value, tb, limit=limit, capture_locals=capture_locals
            ).format()
        )
        content_type = testtools.content.ContentType(
            "text", "x-traceback", {"language": "python", "charset": "utf8"}
        )
        super().__init__(
            content_type, lambda: [x.encode("utf8") for x in stack_lines]
        )


testtools.content.TracebackContent = MAASTracebackContent

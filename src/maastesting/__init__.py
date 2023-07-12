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
        environ.get("MAAS_WAIT_FOR_REACTOR", 60.0)
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

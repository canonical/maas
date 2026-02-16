# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os

import pytest


def skip_if_integration_disabled():
    """
    Helper function to determine whether to run integration tests based on an environment variable.
    By default, integration tests are executed unless the environment variable RUN_INTEGRATION_TESTS is set to '0'.
    """
    env = os.environ.get("RUN_INTEGRATION_TESTS", "1")

    return pytest.mark.skipif(
        env == "0", reason="Integration tests are skipped."
    )

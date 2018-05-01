# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Running settings for the current process."""

from provisioningserver.config import (
    ClusterConfiguration,
    is_dev_environment,
)

# Running in debug mode?
DEBUG = False


# Override defaults with configuration options.
with ClusterConfiguration.open() as config:
    DEBUG = config.debug

# Debug mode is always on in the development environment.
if is_dev_environment():
    DEBUG = True

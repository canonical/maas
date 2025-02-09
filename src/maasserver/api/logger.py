# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API logger."""

from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("api")

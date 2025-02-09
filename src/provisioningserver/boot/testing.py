# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for `provisioningserver.boot`."""

from typing import Dict, Optional, Tuple

from provisioningserver.utils.tftp import TFTPPath

# Components of the TFTP path, perhaps obtained from a regex match.
TFTPPathComponents = Dict[str, Optional[bytes]]

# Type hint for get_example_path_and_components() functions.
TFTPPathAndComponents = Tuple[TFTPPath, TFTPPathComponents]

#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Expose `snippets` as a top-level package for this directory's tests.

`maas_run_remote_scripts.py`/`maas_run_scripts.py` fall back to
`from snippets.maas_api_helper import ...` when `maas_api_helper` isn't
importable directly - the production code path exercised when these
scripts run standalone on a target machine, outside the MAAS source
tree. Relocating their tests out of `metadataserver/user_data/templates/`
(a non-package directory, previously the pytest rootdir-insertion
source of `snippets`) means that fallback import would otherwise fail
with `ModuleNotFoundError`, so `templates/` is added back onto
`sys.path` here, scoped to this directory only.
"""

import os
import sys

import metadataserver

_production_templates_dir = os.path.join(
    os.path.dirname(metadataserver.__file__), "user_data", "templates"
)
sys.path.insert(0, _production_templates_dir)

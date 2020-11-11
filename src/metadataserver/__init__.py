# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata service application."""


import logging

logger = logging.getLogger("metadataserver")


class DefaultMeta:
    """Base class for model `Meta` classes in the metadataserver app.

    Each model in the models package outside of __init__.py needs a nested
    `Meta` class that defines `app_label`.  Otherwise, South won't recognize
    the model and will fail to generate schema migrations for it.
    """

    app_label = "metadataserver"

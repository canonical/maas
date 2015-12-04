# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""An API client."""

__all__ = []


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass

# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAAS-specific test HTTP client."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MAASSensibleClient',
    ]

from maasserver.utils.orm import (
    post_commit_hooks,
    transactional,
    )
from maastesting.djangoclient import SensibleClient


class MAASSensibleClient(SensibleClient):
    """A derivative of Django's test client specially for MAAS.

    This ensures that requests are performed in a transaction, and that
    post-commit hooks are alway fired or reset.
    """

    def request(self, **request):
        # Make sure that requests are done within a transaction. Some kinds of
        # tests will already have a transaction in progress, in which case
        # this will act like a sub-transaction, but that's fine.
        upcall = transactional(super(MAASSensibleClient, self).request)
        # If we're outside of a transaction right now then the transactional()
        # wrapper above will ensure that post-commit hooks are run or reset on
        # return from the request. However, we want to ensure that post-commit
        # hooks are fired in any case, hence the belt-n-braces context.
        with post_commit_hooks:
            return upcall(**request)

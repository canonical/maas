# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Abstract handler class for a ViewModel. All fields are read-only."""

from maasserver.websockets.base import Handler


class ViewModelHandler(Handler):
    class Meta:
        abstract = True

    def create(self, params):
        raise NotImplementedError("Cannot create a ViewModel object.")

    def update(self, params):
        raise NotImplementedError("Cannot update a ViewModel object.")

    def delete(self, params):
        raise NotImplementedError("Cannot delete a ViewModel object.")

# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Notification form."""

from maasserver.forms import MAASModelForm
from maasserver.models.notification import Notification


class NotificationForm(MAASModelForm):
    """Notification creation/edit form."""

    class Meta:
        model = Notification
        fields = (
            "ident",
            "user",
            "users",
            "admins",
            "message",
            "context",
            "category",
            "dismissable",
        )

    def clean_context(self):
        data = self.cleaned_data.get("context")
        if data is None:
            return {}
        elif isinstance(data, str):
            if len(data) == 0 or data.isspace():
                return {}
            else:
                return data
        else:
            return data

    def clean_dismissable(self):
        data = self.data.get("dismissable")
        return data in (None, "true")

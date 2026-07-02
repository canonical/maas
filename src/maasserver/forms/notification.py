# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Notification form."""

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from maasserver.forms import MAASModelForm
from maasserver.models.notification import Notification


class NotificationForm(MAASModelForm):
    """Notification creation/edit form."""

    # Override user ForeignKey field with CharField to accept both numeric IDs
    # and alphanumeric usernames. Django's auto-generated ModelChoiceField would
    # reject non-numeric strings before clean_user() could resolve them.
    user = forms.CharField(required=False)

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

    def clean_user(self):
        raw_user = self.cleaned_data.get("user", "").strip()

        if not raw_user:
            return None

        # If numeric, treat as user ID (existing behavior).
        if raw_user.isdigit():
            try:
                return User.objects.get(pk=int(raw_user))
            except User.DoesNotExist:
                raise ValidationError(
                    "Enter a valid user id or username."
                ) from None

        # Non-numeric: treat as username.
        try:
            return User.objects.get(username=raw_user)
        except User.DoesNotExist:
            raise ValidationError(
                "Enter a valid user id or username."
            ) from None

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

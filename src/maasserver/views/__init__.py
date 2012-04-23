# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "HelpfulDeleteView",
    "process_form",
    "AccountsEdit",
    "AccountsView",
    "settings",
    "settings_add_archive",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    )

from django.contrib import messages
from django.http import (
    Http404,
    HttpResponseRedirect,
    )
from django.views.generic import DeleteView


class HelpfulDeleteView(DeleteView):
    """Extension to Django's :class:`django.views.generic.DeleteView`.

    This modifies `DeleteView` in a few ways:
     - Deleting a nonexistent object is considered successful.
     - There's a callback that lets you describe the object to the user.
     - User feedback is built in.
     - get_success_url defaults to returning the "next" URL.
     - Confirmation screen also deals nicely with already-deleted object.

    :ivar model: The model class this view is meant to delete.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_object(self):
        """Retrieve the object to be deleted."""

    @abstractmethod
    def get_next_url(self):
        """URL of page to proceed to after deleting."""

    def delete(self, *args, **kwargs):
        """Delete result of self.get_object(), if any."""
        try:
            self.object = self.get_object()
        except Http404:
            feedback = self.compose_feedback_nonexistent()
        else:
            self.object.delete()
            feedback = self.compose_feedback_deleted(self.object)
        return self.move_on(feedback)

    def get(self, *args, **kwargs):
        """Prompt for confirmation of deletion request in the UI.

        This is where the view acts as a regular template view.

        If the object has been deleted in the meantime though, don't bother:
        we'll just redirect to the next URL and show a notice that the object
        is no longer there.
        """
        try:
            return super(HelpfulDeleteView, self).get(*args, **kwargs)
        except Http404:
            return self.move_on(self.compose_feedback_nonexistent())

    def compose_feedback_nonexistent(self):
        """Compose feedback message: "obj was already deleted"."""
        return "Not deleting: %s not found." % self.model._meta.verbose_name

    def compose_feedback_deleted(self, obj):
        """Compose feedback message: "obj has been deleted"."""
        return ("%s deleted." % self.name_object(obj)).capitalize()

    def name_object(self, obj):
        """Overridable: describe object being deleted to the user.

        The result text will be included in a user notice along the lines of
        "<Object> deleted."

        :param obj: Object that's been deleted from the database.
        :return: Description of the object, along the lines of
            "User <obj.username>".
        """
        return obj._meta.verbose_name

    def show_notice(self, notice):
        """Wrapper for messages.info."""
        messages.info(self.request, notice)

    def move_on(self, feedback_message):
        """Redirect to the post-deletion page, showing the given message."""
        self.show_notice(feedback_message)
        return HttpResponseRedirect(self.get_next_url())


def process_form(request, form_class, redirect_url, prefix,
                 success_message=None, form_kwargs=None):
    """Utility method to process subforms (i.e. forms with a prefix).

    :param request: The request which contains the data to be validated.
    :type request: django.http.HttpRequest
    :param form_class: The form class used to perform the validation.
    :type form_class: django.forms.Form
    :param redirect_url: The url where the user should be redirected if the
        form validates successfully.
    :type redirect_url: basestring
    :param prefix: The prefix of the form.
    :type prefix: basestring
    :param success_message: An optional message that will be displayed if the
        form validates successfully.
    :type success_message: basestring
    :param form_kwargs: An optional dict that will passed to the form creation
        method.
    :type form_kwargs: dict or None
    :return: A tuple of the validated form and a response (the response will
        not be None only if the form has been validated correctly).
    :rtype: tuple

    """
    if form_kwargs is None:
        form_kwargs = {}
    if '%s_submit' % prefix in request.POST:
        form = form_class(
            data=request.POST, prefix=prefix, **form_kwargs)
        if form.is_valid():
            if success_message is not None:
                messages.info(request, success_message)
            form.save()
            return form, HttpResponseRedirect(redirect_url)
    else:
        form = form_class(prefix=prefix, **form_kwargs)
    return form, None

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
    "AccountsAdd",
    "AccountsDelete",
    "AccountsEdit",
    "AccountsView",
    "combo_view",
    "settings",
    "settings_add_archive",
    "SSHKeyCreateView",
    "SSHKeyDeleteView",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    )
import os

from convoy.combo import (
    combine_files,
    parse_qs,
    )
from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.forms import (
    AdminPasswordChangeForm,
    PasswordChangeForm,
    )
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotFound,
    HttpResponseRedirect,
    )
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    )
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin
from maasserver.exceptions import CannotDeleteUserException
from maasserver.forms import (
    AddArchiveForm,
    CommissioningForm,
    EditUserForm,
    MAASAndNetworkForm,
    NewUserCreationForm,
    ProfileForm,
    SSHKeyForm,
    UbuntuForm,
    )
from maasserver.models import (
    SSHKey,
    UserProfile,
    )


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


class SSHKeyCreateView(CreateView):

    form_class = SSHKeyForm
    template_name = 'maasserver/prefs_add_sshkey.html'

    def get_form_kwargs(self):
        kwargs = super(SSHKeyCreateView, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.info(self.request, "SSH key added.")
        return super(SSHKeyCreateView, self).form_valid(form)

    def get_success_url(self):
        return reverse('prefs')


class SSHKeyDeleteView(HelpfulDeleteView):

    template_name = 'maasserver/prefs_confirm_delete_sshkey.html'
    context_object_name = 'key'
    model = SSHKey

    def get_object(self):
        keyid = self.kwargs.get('keyid', None)
        key = get_object_or_404(SSHKey, id=keyid)
        if key.user != self.request.user:
            raise PermissionDenied("Can't delete this key.  It's not yours.")
        return key

    def get_next_url(self):
        return reverse('prefs')


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


def userprefsview(request):
    user = request.user
    # Process the profile update form.
    profile_form, response = process_form(
        request, ProfileForm, reverse('prefs'), 'profile', "Profile updated.",
        {'instance': user})
    if response is not None:
        return response

    # Process the password change form.
    password_form, response = process_form(
        request, PasswordChangeForm, reverse('prefs'), 'password',
        "Password updated.", {'user': user})
    if response is not None:
        return response

    return render_to_response(
        'maasserver/prefs.html',
        {
            'profile_form': profile_form,
            'password_form': password_form,
        },
        context_instance=RequestContext(request))


class AccountsView(DetailView):
    """Read-only view of user's account information."""

    template_name = 'maasserver/user_view.html'

    context_object_name = 'view_user'

    def get_object(self):
        username = self.kwargs.get('username', None)
        user = get_object_or_404(User, username=username)
        return user


class AccountsAdd(CreateView):
    """Add-user view."""

    form_class = NewUserCreationForm

    template_name = 'maasserver/user_add.html'

    context_object_name = 'new_user'

    def get_success_url(self):
        return reverse('settings')

    def form_valid(self, form):
        messages.info(self.request, "User added.")
        return super(AccountsAdd, self).form_valid(form)


class AccountsDelete(DeleteView):

    template_name = 'maasserver/user_confirm_delete.html'
    context_object_name = 'user_to_delete'

    def get_object(self):
        username = self.kwargs.get('username', None)
        user = get_object_or_404(User, username=username)
        return user.get_profile()

    def get_next_url(self):
        return reverse('settings')

    def delete(self, request, *args, **kwargs):
        profile = self.get_object()
        username = profile.user.username
        try:
            profile.delete()
            messages.info(request, "User %s deleted." % username)
        except CannotDeleteUserException as e:
            messages.info(request, unicode(e))
        return HttpResponseRedirect(self.get_next_url())


class AccountsEdit(TemplateView, ModelFormMixin,
                   SingleObjectTemplateResponseMixin):

    model = User
    template_name = 'maasserver/user_edit.html'

    def get_object(self):
        username = self.kwargs.get('username', None)
        return get_object_or_404(User, username=username)

    def respond(self, request, profile_form, password_form):
        """Generate a response."""
        return self.render_to_response({
            'profile_form': profile_form,
            'password_form': password_form,
            })

    def get(self, request, *args, **kwargs):
        """Called by `TemplateView`: handle a GET request."""
        self.object = user = self.get_object()
        profile_form = EditUserForm(instance=user, prefix='profile')
        password_form = AdminPasswordChangeForm(user=user, prefix='password')
        return self.respond(request, profile_form, password_form)

    def post(self, request, *args, **kwargs):
        """Called by `TemplateView`: handle a POST request."""
        self.object = user = self.get_object()
        next_page = reverse('settings')

        # Process the profile-editing form, if that's what was submitted.
        profile_form, response = process_form(
            request, EditUserForm, next_page, 'profile', "Profile updated.",
            {'instance': user})
        if response is not None:
            return response

        # Process the password change form, if that's what was submitted.
        password_form, response = process_form(
            request, AdminPasswordChangeForm, next_page, 'password',
            "Password updated.", {'user': user})
        if response is not None:
            return response

        return self.respond(request, profile_form, password_form)


def settings(request):
    user_list = UserProfile.objects.all_users().order_by('username')
    # Process the MAAS & network form.
    maas_and_network_form, response = process_form(
        request, MAASAndNetworkForm, reverse('settings'), 'maas_and_network',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the Commissioning form.
    commissioning_form, response = process_form(
        request, CommissioningForm, reverse('settings'), 'commissioning',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the Ubuntu form.
    ubuntu_form, response = process_form(
        request, UbuntuForm, reverse('settings'), 'ubuntu',
        "Configuration updated.")
    if response is not None:
        return response

    return render_to_response(
        'maasserver/settings.html',
        {
            'user_list': user_list,
            'maas_and_network_form': maas_and_network_form,
            'commissioning_form': commissioning_form,
            'ubuntu_form': ubuntu_form,
        },
        context_instance=RequestContext(request))


def settings_add_archive(request):
    if request.method == 'POST':
        form = AddArchiveForm(request.POST)
        if form.is_valid():
            form.save()
            messages.info(request, "Archive added.")
            return HttpResponseRedirect(reverse('settings'))
    else:
        form = AddArchiveForm()

    return render_to_response(
        'maasserver/settings_add_archive.html',
        {'form': form},
        context_instance=RequestContext(request))


def get_yui_location():
    if django_settings.STATIC_ROOT:
        return os.path.join(
            django_settings.STATIC_ROOT, 'jslibs', 'yui')
    else:
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'static',
            'jslibs', 'yui')


def combo_view(request):
    """Handle a request for combining a set of files."""
    fnames = parse_qs(request.META.get("QUERY_STRING", ""))
    YUI_LOCATION = get_yui_location()

    if fnames:
        if fnames[0].endswith('.js'):
            content_type = 'text/javascript; charset=UTF-8'
        elif fnames[0].endswith('.css'):
            content_type = 'text/css'
        else:
            return HttpResponseBadRequest("Invalid file type requested.")
        content = b"".join(
            combine_files(
               fnames, YUI_LOCATION, resource_prefix='/',
               rewrite_urls=True))

        return HttpResponse(
            content_type=content_type, status=200, content=content)

    return HttpResponseNotFound()

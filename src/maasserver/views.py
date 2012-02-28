# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "logout",
    "NodeListView",
    "NodesCreateView",
    ]

from django.contrib import messages
from django.contrib.auth.forms import PasswordChangeForm as PasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.views import logout as dj_logout
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
    )
from maasserver.exceptions import CannotDeleteUserException
from maasserver.forms import (
    EditUserForm,
    MaaSAndNetworkForm,
    NewUserCreationForm,
    ProfileForm,
    )
from maasserver.models import (
    Node,
    UserProfile,
    )


def logout(request):
    messages.info(request, "You have been logged out.")
    return dj_logout(request, next_page=reverse('login'))


class NodeListView(ListView):

    context_object_name = "node_list"

    def get_queryset(self):
        return Node.objects.get_visible_nodes(user=self.request.user)


class NodesCreateView(CreateView):

    model = Node

    def get_success_url(self):
        return reverse('index')


def userprefsview(request):
    user = request.user
    # Process the profile update form.
    if 'profile_submit' in request.POST:
        profile_form = ProfileForm(
            request.POST, instance=user, prefix='profile')
        if profile_form.is_valid():
            messages.info(request, "Profile updated.")
            profile_form.save()
            return HttpResponseRedirect(reverse('prefs'))
    else:
        profile_form = ProfileForm(instance=user, prefix='profile')

    # Process the password change form.
    if 'password_submit' in request.POST:
        password_form = PasswordForm(
            data=request.POST, user=user, prefix='password')
        if password_form.is_valid():
            messages.info(request, "Password updated.")
            password_form.save()
            return HttpResponseRedirect(reverse('prefs'))
    else:
        password_form = PasswordForm(user=user, prefix='password')

    return render_to_response(
        'maasserver/prefs.html',
        {
            'profile_form': profile_form,
            'password_form': password_form,
        },
        context_instance=RequestContext(request))


class AccountsView(DetailView):

    template_name = 'maasserver/user_view.html'

    context_object_name = 'view_user'

    def get_object(self):
        username = self.kwargs.get('username', None)
        user = get_object_or_404(User, username=username)
        return user


class AccountsAdd(CreateView):

    form_class = NewUserCreationForm

    template_name = 'maasserver/user_add.html'

    context_object_name = 'new_user'

    def get_success_url(self):
        return reverse('settings')


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


class AccountsEdit(UpdateView):

    form_class = EditUserForm

    template_name = 'maasserver/user_edit.html'

    def get_object(self):
        username = self.kwargs.get('username', None)
        user = get_object_or_404(User, username=username)
        return user

    def get_success_url(self):
        return reverse('settings')


def settings(request):
    user_list = UserProfile.objects.all_users().order_by('username')
    # Process the MaaS & network form.
    if 'maas_and_network_submit' in request.POST:
        maas_and_network_form = MaaSAndNetworkForm(
            request.POST, prefix='maas_and_network')
        if maas_and_network_form.is_valid():
            messages.info(request, "Configuration updated.")
            maas_and_network_form.save()
            return HttpResponseRedirect(reverse('settings'))
    else:
        maas_and_network_form = MaaSAndNetworkForm(
            prefix='maas_and_network')

    return render_to_response(
        'maasserver/settings.html',
        {
            'user_list': user_list,
            'maas_and_network_form': maas_and_network_form,
        },
        context_instance=RequestContext(request))

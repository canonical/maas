# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Views."""

from __future__ import (
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
    "login",
    "logout",
    "NodeListView",
    "NodesCreateView",
    "NodeView",
    "NodeEdit",
    "settings",
    "settings_add_archive",
    "SSHKeyCreateView",
    "SSHKeyDeleteView",
    ]

from logging import getLogger
import mimetypes
import os
import urllib2

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
from django.contrib.auth.views import (
    login as dj_login,
    logout as dj_logout,
    )
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import (
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
    ListView,
    UpdateView,
    )
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin
from maasserver.exceptions import (
    CannotDeleteUserException,
    NoRabbit,
    )
from maasserver.forms import (
    AddArchiveForm,
    CommissioningForm,
    EditUserForm,
    get_action_form,
    MAASAndNetworkForm,
    NewUserCreationForm,
    ProfileForm,
    SSHKeyForm,
    UbuntuForm,
    UIAdminNodeEditForm,
    UINodeEditForm,
    )
from maasserver.messages import messaging
from maasserver.models import (
    Node,
    NODE_PERMISSION,
    NODE_STATUS,
    SSHKey,
    UserProfile,
    )


def login(request):
    extra_context = {
        'no_users': UserProfile.objects.all_users().count() == 0,
        'create_command': django_settings.MAAS_CLI,
        }
    return dj_login(request, extra_context=extra_context)


def logout(request):
    messages.info(request, "You have been logged out.")
    return dj_logout(request, next_page=reverse('login'))


class NodeView(UpdateView):

    template_name = 'maasserver/node_view.html'

    context_object_name = 'node'

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.VIEW)
        return node

    def get_form_class(self):
        return get_action_form(self.request.user, self.request)

    def get_context_data(self, **kwargs):
        context = super(NodeView, self).get_context_data(**kwargs)
        node = self.get_object()
        context['can_edit'] = self.request.user.has_perm(
            NODE_PERMISSION.EDIT, node)
        context['can_delete'] = self.request.user.has_perm(
            NODE_PERMISSION.ADMIN, node)
        return context

    def get_success_url(self):
        return reverse('node-view', args=[self.get_object().system_id])


class NodeEdit(UpdateView):

    template_name = 'maasserver/node_edit.html'

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.EDIT)
        return node

    def get_form_class(self):
        if self.request.user.is_superuser:
            return UIAdminNodeEditForm
        else:
            return UINodeEditForm

    def get_success_url(self):
        return reverse('node-view', args=[self.get_object().system_id])


class NodeDelete(DeleteView):

    template_name = 'maasserver/node_confirm_delete.html'

    context_object_name = 'node_to_delete'

    def get_object(self):
        system_id = self.kwargs.get('system_id', None)
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=self.request.user,
            perm=NODE_PERMISSION.ADMIN)
        if node.status == NODE_STATUS.ALLOCATED:
            raise PermissionDenied()
        return node

    def get_next_url(self):
        return reverse('node-list')

    def delete(self, request, *args, **kwargs):
        node = self.get_object()
        node.delete()
        messages.info(request, "Node %s deleted." % node.system_id)
        return HttpResponseRedirect(self.get_next_url())


def get_longpoll_context():
    if messaging is not None and django_settings.LONGPOLL_PATH is not None:
        try:
            return {
                'longpoll_queue': messaging.getQueue().name,
                'LONGPOLL_PATH': django_settings.LONGPOLL_PATH,
                }
        except NoRabbit as e:
            getLogger('maasserver').warn(
                "Could not connect to RabbitMQ: %s", e)
            return {}
    else:
        return {}


class NodeListView(ListView):

    context_object_name = "node_list"

    def get_queryset(self):
        return Node.objects.get_nodes(
            user=self.request.user, perm=NODE_PERMISSION.VIEW)

    def get_context_data(self, **kwargs):
        context = super(NodeListView, self).get_context_data(**kwargs)
        context.update(get_longpoll_context())
        return context


class NodesCreateView(CreateView):

    model = Node

    def get_success_url(self):
        return reverse('index')


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


class SSHKeyDeleteView(DeleteView):

    template_name = 'maasserver/prefs_confirm_delete_sshkey.html'
    context_object_name = 'key'

    def get_object(self):
        keyid = self.kwargs.get('keyid', None)
        return get_object_or_404(SSHKey, user=self.request.user, id=keyid)

    def form_valid(self, form):
        messages.info(self.request, "SSH key deleted.")
        return super(SSHKeyDeleteView, self).form_valid(form)

    def get_success_url(self):
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


def proxy_to_longpoll(request):
    url = django_settings.LONGPOLL_SERVER_URL
    assert url is not None, (
        "LONGPOLL_SERVER_URL should point to a Longpoll server.")

    if 'QUERY_STRING' in request.META:
        url += '?' + request.META['QUERY_STRING']
    proxied_response = urllib2.urlopen(url)
    status_code = proxied_response.code
    mimetype = (
        proxied_response.headers.typeheader or mimetypes.guess_type(url))
    content = proxied_response.read()
    return HttpResponse(content, status=status_code, mimetype=mimetype)


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
            os.path.dirname(__file__), 'static', 'jslibs', 'yui')


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

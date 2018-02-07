# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Settings views."""

__all__ = [
    "AccountsAdd",
    "AccountsDelete",
    "AccountsEdit",
    "AccountsView",
    "settings",
    ]

from django.contrib import messages
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import (
    get_object_or_404,
    render,
)
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
)
from django.views.generic.base import TemplateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin
from maasserver.audit import create_audit_event
from maasserver.clusterrpc.osystems import gen_all_known_operating_systems
from maasserver.enum import ENDPOINT
from maasserver.exceptions import CannotDeleteUserException
from maasserver.forms import (
    CommissioningForm,
    DeployForm,
    DNSForm,
    EditUserForm,
    GlobalKernelOptsForm,
    MAASForm,
    NetworkDiscoveryForm,
    NewUserCreationForm,
    NTPForm,
    ProxyForm,
    StorageSettingsForm,
    ThirdPartyDriversForm,
    UbuntuForm,
    WindowsForm,
)
from maasserver.models import (
    LicenseKey,
    UserProfile,
)
from maasserver.utils.django_urls import reverse
from maasserver.utils.osystems import (
    get_osystem_from_osystems,
    get_release_from_osystem,
)
from maasserver.views import process_form
from metadataserver.enum import SCRIPT_TYPE
from metadataserver.models import Script
from provisioningserver.events import EVENT_TYPES


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
        username = self.request._post['username']
        messages.info(self.request, "User added.")
        create_audit_event(
            EVENT_TYPES.AUTHORISATION, ENDPOINT.UI, self.request, None,
            description=("%s %s" % (
                'Admin' if form.cleaned_data['is_superuser'] else 'User',
                username) + " created by '%(username)s'."))
        return super(AccountsAdd, self).form_valid(form)


class AccountsDelete(DeleteView):

    template_name = 'maasserver/user_confirm_delete.html'
    context_object_name = 'user_to_delete'

    def get_object(self):
        username = self.kwargs.get('username', None)
        user = get_object_or_404(User, username=username)
        return user.userprofile

    def get_next_url(self):
        return reverse('settings')

    def delete(self, request, *args, **kwargs):
        profile = self.get_object()
        username = profile.user.username
        try:
            create_audit_event(
                EVENT_TYPES.AUTHORISATION, ENDPOINT.UI, request, None,
                description=(
                    "%s %s" % (
                        'Admin' if profile.user.is_superuser else 'User',
                        username) + " deleted by '%(username)s'."))
            profile.delete()
            messages.info(request, "User %s deleted." % username)
        except CannotDeleteUserException as e:
            messages.info(request, str(e))
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
            create_audit_event(
                EVENT_TYPES.AUTHORISATION, ENDPOINT.UI, request, None,
                description=(
                    "User profile (username: %s, full name: %s, email: %s, "
                    "administrator: %s)" % (
                        profile_form.cleaned_data['username'],
                        profile_form.cleaned_data['last_name'],
                        profile_form.cleaned_data['email'],
                        profile_form.cleaned_data['is_superuser']) +
                    " updated by '%(username)s'."))
            return response

        # Process the password change form, if that's what was submitted.
        password_form, response = process_form(
            request, AdminPasswordChangeForm, next_page, 'password',
            "Password updated.", {'user': user})
        if response is not None:
            create_audit_event(
                EVENT_TYPES.AUTHORISATION, ENDPOINT.UI, request, None,
                description="Password changed for '%(username)s'.")
            return response

        return self.respond(request, profile_form, password_form)


def has_osystems_supporting_license_keys(osystems):
    """Return True if the given osystems supports releases with license keys.
    """
    for osystem in osystems:
        for release in osystem['releases']:
            if release['requires_license_key']:
                return True
    return False


def set_license_key_titles(license_key, osystems):
    """Sets the osystem_title and distro_series_title field on the
    license_key.

    Uses the given "osystems" to get the titles.
    """
    osystem = get_osystem_from_osystems(osystems, license_key.osystem)
    if osystem is None:
        license_key.osystem_title = license_key.osystem
        license_key.distro_series_title = license_key.distro_series
        return
    license_key.osystem_title = osystem['title']
    release = get_release_from_osystem(osystem, license_key.distro_series)
    if release is None:
        license_key.distro_series_title = license_key.distro_series
        return
    license_key.distro_series_title = release['title']


def settings(request):
    user_list = UserProfile.objects.all_users().order_by('username')

    # Process Third Party Drivers form.
    third_party_drivers_form, response = process_form(
        request, ThirdPartyDriversForm, reverse('settings'),
        'third_party_drivers', "Configuration updated.")
    if response is not None:
        return response

    # Process disk erasing on release form.
    storage_settings_form, response = process_form(
        request, StorageSettingsForm, reverse('settings'),
        'storage_settings', "Configuration updated.")
    if response is not None:
        return response

    # Process the MAAS form.
    maas_form, response = process_form(
        request, MAASForm, reverse('settings'), 'maas',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the network form.
    proxy_form, response = process_form(
        request, ProxyForm, reverse('settings'), 'proxy',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the DNS form.
    dns_form, response = process_form(
        request, DNSForm, reverse('settings'), 'dns',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the NTP form.
    ntp_form, response = process_form(
        request, NTPForm, reverse('settings'), 'ntp',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the network discovery form.
    network_discovery_form, response = process_form(
        request, NetworkDiscoveryForm, reverse('settings'),
        'network_discovery', "Configuration updated.")
    if response is not None:
        return response

    # Process the Commissioning form.
    commissioning_form, response = process_form(
        request, CommissioningForm, reverse('settings'), 'commissioning',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the Deploy form.
    deploy_form, response = process_form(
        request, DeployForm, reverse('settings'), 'deploy',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the Ubuntu form.
    ubuntu_form, response = process_form(
        request, UbuntuForm, reverse('settings'), 'ubuntu',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the Windows form.
    windows_form, response = process_form(
        request, WindowsForm, reverse('settings'), 'windows',
        "Configuration updated.")
    if response is not None:
        return response

    # Process the Global Kernel Opts form.
    kernelopts_form, response = process_form(
        request, GlobalKernelOptsForm, reverse('settings'), 'kernelopts',
        "Configuration updated.")
    if response is not None:
        return response

    # Commissioning scripts.
    commissioning_scripts = Script.objects.filter(
        script_type=SCRIPT_TYPE.COMMISSIONING)

    # Test scripts.
    test_scripts = Script.objects.filter(
        script_type=SCRIPT_TYPE.TESTING, default=False)

    # License keys w/ titles for osystem and distro_series
    osystems = list(gen_all_known_operating_systems())
    show_license_keys = has_osystems_supporting_license_keys(osystems)
    license_keys = LicenseKey.objects.all()
    for license_key in license_keys:
        set_license_key_titles(license_key, osystems)

    return render(
        request,
        'maasserver/settings.html',
        {
            'user_list': user_list,
            'commissioning_scripts': commissioning_scripts,
            'test_scripts': test_scripts,
            'show_license_keys': show_license_keys,
            'license_keys': license_keys,
            'maas_form': maas_form,
            'proxy_form': proxy_form,
            'dns_form': dns_form,
            'ntp_form': ntp_form,
            'network_discovery_form': network_discovery_form,
            'third_party_drivers_form': third_party_drivers_form,
            'storage_settings_form': storage_settings_form,
            'commissioning_form': commissioning_form,
            'deploy_form': deploy_form,
            'ubuntu_form': ubuntu_form,
            'windows_form': windows_form,
            'kernelopts_form': kernelopts_form,
        })

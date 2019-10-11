# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""URL routing configuration."""

__all__ = []


from django.conf.urls import include, url
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse
from maasserver import urls_api, urls_combo
from maasserver.bootresources import (
    simplestreams_file_handler,
    simplestreams_stream_handler,
)
from maasserver.macaroon_auth import MacaroonDischargeRequest
from maasserver.prometheus.stats import prometheus_stats_handler
from maasserver.views import settings, TextTemplateView
from maasserver.views.account import authenticate, csrf, login, logout
from maasserver.views.index import IndexView
from maasserver.views.prefs import (
    SSLKeyCreateView,
    SSLKeyDeleteView,
    userprefsview,
)
from maasserver.views.rpc import info
from maasserver.views.settings import (
    AccountsAdd,
    AccountsDelete,
    AccountsEdit,
    AccountsView,
)
from maasserver.views.settings_commissioning_scripts import (
    CommissioningScriptCreate,
    CommissioningScriptDelete,
)
from maasserver.views.settings_license_keys import (
    LicenseKeyCreate,
    LicenseKeyDelete,
    LicenseKeyEdit,
)
from maasserver.views.settings_test_scripts import (
    TestScriptCreate,
    TestScriptDelete,
)


def adminurl(regexp, view, *args, **kwargs):
    view = user_passes_test(lambda u: u.is_superuser)(view)
    return url(regexp, view, *args, **kwargs)


# # URLs accessible to anonymous users.
# Combo URLs.
urlpatterns = [url(r"combo/", include(urls_combo))]

# Anonymous views.
urlpatterns += [
    url(r"^accounts/login/$", login, name="login"),
    url(r"^accounts/authenticate/$", authenticate, name="authenticate"),
    url(
        r"^accounts/discharge-request/$",
        MacaroonDischargeRequest(),
        name="discharge-request",
    ),
    url(
        r"^images-stream/streams/v1/(?P<filename>.*)$",
        simplestreams_stream_handler,
        name="simplestreams_stream_handler",
    ),
    url(
        r"^images-stream/(?P<os>.*)/(?P<arch>.*)/(?P<subarch>.*)/"
        "(?P<series>.*)/(?P<version>.*)/(?P<filename>.*)$",
        simplestreams_file_handler,
        name="simplestreams_file_handler",
    ),
    url(r"^metrics$", prometheus_stats_handler, name="metrics"),
    url(
        r"^robots\.txt$",
        TextTemplateView.as_view(template_name="maasserver/robots.txt"),
        name="robots",
    ),
]

# # URLs for logged-in users.
# Preferences views.
urlpatterns += [
    url(r"^account/csrf/$", csrf, name="csrf"),
    url(r"^account/prefs/$", userprefsview, name="prefs"),
    url(
        r"^account/prefs/sslkey/add/$",
        SSLKeyCreateView.as_view(),
        name="prefs-add-sslkey",
    ),
    url(
        r"^account/prefs/sslkey/delete/(?P<keyid>\d*)/$",
        SSLKeyDeleteView.as_view(),
        name="prefs-delete-sslkey",
    ),
]
# Logout view.
urlpatterns += [url(r"^accounts/logout/$", logout, name="logout")]


# Index view.
urlpatterns += [url(r"^$", IndexView.as_view(), name="index")]

# # URLs for admin users.
# Settings views.
urlpatterns += [
    adminurl(r"^settings/$", settings.settings, name="settings"),
    adminurl(r"^settings/users/$", settings.users, name="settings_users"),
    adminurl(
        r"^settings/general/$", settings.general, name="settings_general"
    ),
    adminurl(
        r"^settings/scripts/$", settings.scripts, name="settings_scripts"
    ),
    adminurl(
        r"^settings/storage/$", settings.storage, name="settings_storage"
    ),
    adminurl(
        r"^settings/network/$", settings.network, name="settings_network"
    ),
    adminurl(
        r"^settings/license-keys/$",
        settings.license_keys,
        name="settings_license_keys",
    ),
    adminurl(r"^accounts/add/$", AccountsAdd.as_view(), name="accounts-add"),
    adminurl(
        r"^accounts/(?P<username>[^/]+)/edit/$",
        AccountsEdit.as_view(),
        name="accounts-edit",
    ),
    adminurl(
        r"^accounts/(?P<username>[^/]+)/view/$",
        AccountsView.as_view(),
        name="accounts-view",
    ),
    adminurl(
        r"^accounts/(?P<username>[^/]+)/del/$",
        AccountsDelete.as_view(),
        name="accounts-del",
    ),
    adminurl(
        r"^commissioning-scripts/(?P<id>[\w\-]+)/delete/$",
        CommissioningScriptDelete.as_view(),
        name="commissioning-script-delete",
    ),
    adminurl(
        r"^commissioning-scripts/add/$",
        CommissioningScriptCreate.as_view(),
        name="commissioning-script-add",
    ),
    adminurl(
        r"^test-scripts/(?P<id>[\w\-]+)/delete/$",
        TestScriptDelete.as_view(),
        name="test-script-delete",
    ),
    adminurl(
        r"^test-scripts/add/$",
        TestScriptCreate.as_view(),
        name="test-script-add",
    ),
    adminurl(
        r"^license-key/(?P<osystem>[^/]+)/(?P<distro_series>[^/]+)/delete/$",
        LicenseKeyDelete.as_view(),
        name="license-key-delete",
    ),
    adminurl(
        r"^license-key/(?P<osystem>[^/]+)/(?P<distro_series>[^/]+)/edit/$",
        LicenseKeyEdit.as_view(),
        name="license-key-edit",
    ),
    adminurl(
        r"^license-key/add/$",
        LicenseKeyCreate.as_view(),
        name="license-key-add",
    ),
]

# API URLs. If old API requested, provide error message directing to new API.
urlpatterns += [
    url(r"^api/2\.0/", include(urls_api)),
    url(
        r"^api/version/",
        lambda request: HttpResponse(content="2.0", content_type="text/plain"),
        name="api_version",
    ),
    url(
        r"^api/1.0/",
        lambda request: HttpResponse(
            content_type="text/plain",
            status=410,
            content="The 1.0 API is no longer available. "
            "Please use API version 2.0.",
        ),
        name="api_v1_error",
    ),
]


# RPC URLs.
urlpatterns += [url(r"^rpc/$", info, name="rpc-info")]

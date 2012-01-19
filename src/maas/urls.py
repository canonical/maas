
from django.conf import settings
from django.conf.urls.defaults import *


urlpatterns = patterns('',
    url(r'^', include('maasserver.urls')),
)

if settings.STATIC_LOCAL_SERVE:
    urlpatterns += patterns('',
        (r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT}),
    )

if settings.DEBUG:
    from django.contrib import admin
    admin.autodiscover()

    urlpatterns += patterns('',
        (r'^admin/', include(admin.site.urls)),
        (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    )


from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    url(r'^', include('maasserver.urls')),
)

if settings.DEBUG:
    from django.contrib import admin
    admin.autodiscover()

    urlpatterns += patterns('',
        (r'^media/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.MEDIA_ROOT}),
        (r'^admin/', include(admin.site.urls)),
        (r'^admin/doc/', include('django.contrib.admindocs.urls')),
    )


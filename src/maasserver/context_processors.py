from django.conf import settings


def yui(context):
    return {
        'YUI_DEBUG': settings.YUI_DEBUG,
        'YUI_VERSION': settings.YUI_VERSION,
    }

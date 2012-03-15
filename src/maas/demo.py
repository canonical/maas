# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django DEMO settings for maas project."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type

import os

# FIRST: developement settings should override base settings.
from maas.settings import *

from maas.development import *


MEDIA_ROOT = os.path.join(os.getcwd(), "media/demo")

MIDDLEWARE_CLASSES += (
    'debug_toolbar.middleware.DebugToolbarMiddleware',
)

# In dev mode: Django should act as a proxy to txlongpoll.
LONGPOLL_SERVER_URL = "http://localhost:8002/"

# Disable longpoll by default for now. Set it back to 'longpoll/' to
# enable it.
LONGPOLL_URL = None

# This should match the setting in /etc/pserv.yaml.
PSERV_URL = "http://localhost:8001/api"

RABBITMQ_PUBLISH = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(levelname)s %(asctime)s %(name)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'maas': {
            'handlers': ['console'],
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'propagate': True,
        },
     }
}

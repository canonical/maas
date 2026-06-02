import os

DEBUG = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "/tmp/piston.db",
    }
}
DATABASE_ENGINE = "sqlite3"
DATABASE_NAME = "/tmp/piston.db"
INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.admin",
    "piston3",
    "test_project.apps.testapp",
)
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(os.path.dirname(__file__), "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

SITE_ID = 1
ROOT_URLCONF = "test_project.urls"

MIDDLEWARE = (
    "piston3.middleware.ConditionalMiddlewareCompatProxy",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "piston3.middleware.CommonMiddlewareCompatProxy",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
)

SECRET_KEY = "bla"

FIXTURE_DIRS = (os.path.join(os.path.dirname(__file__), "..", "fixtures"),)

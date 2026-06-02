import time
from urllib.parse import (
    urlencode,
    urlparse,
    urlunparse,
)

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

from .managers import (
    ConsumerManager,
    TokenManager,
)
from .utils import make_random_password

KEY_SIZE = 18
SECRET_SIZE = 32
VERIFIER_SIZE = 10

CONSUMER_STATES = (
    ("pending", "Pending"),
    ("accepted", "Accepted"),
    ("canceled", "Canceled"),
    ("rejected", "Rejected"),
)


AUTH_USER_MODEL = getattr(settings, "AUTH_USER_MODEL", User)


def generate_random(length=SECRET_SIZE):
    return make_random_password(length=length)


def get_default_timestamp():
    return int(time.time())


class Nonce(models.Model):
    token_key = models.CharField(max_length=KEY_SIZE)
    consumer_key = models.CharField(max_length=KEY_SIZE)
    key = models.CharField(max_length=255)

    def __unicode__(self):
        return f"Nonce {self.key} for {self.consumer_key}"

    class Meta:
        # This is mostly useful to speed up Nonces lookups, as the table can
        # grow quite large and full scans are expensive
        unique_together = (["token_key", "consumer_key", "key"],)


class Consumer(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()

    key = models.CharField(max_length=KEY_SIZE)
    secret = models.CharField(max_length=SECRET_SIZE)

    status = models.CharField(
        max_length=16, choices=CONSUMER_STATES, default="pending"
    )
    user = models.ForeignKey(
        AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="consumers",
        on_delete=models.CASCADE,
    )

    objects = ConsumerManager()

    def __unicode__(self):
        return f"Consumer {self.name} with key {self.key}"

    def generate_random_codes(self):
        """
        Used to generate random key/secret pairings. Use this after you've
        added the other data in place of save().

        c = Consumer()
        c.name = "My consumer"
        c.description = "An app that makes ponies from the API."
        c.user = some_user_object
        c.generate_random_codes()
        """
        key = make_random_password(length=KEY_SIZE)
        secret = generate_random(SECRET_SIZE)

        while Consumer.objects.filter(
            key__exact=key, secret__exact=secret
        ).count():
            secret = generate_random(SECRET_SIZE)

        self.key = key
        self.secret = secret
        self.save()


class Token(models.Model):
    REQUEST = 1
    ACCESS = 2
    TOKEN_TYPES = ((REQUEST, "Request"), (ACCESS, "Access"))

    key = models.CharField(max_length=KEY_SIZE)
    secret = models.CharField(max_length=SECRET_SIZE)
    verifier = models.CharField(max_length=VERIFIER_SIZE)
    token_type = models.IntegerField(choices=TOKEN_TYPES)
    timestamp = models.IntegerField(default=get_default_timestamp)
    is_approved = models.BooleanField(default=False)

    user = models.ForeignKey(
        AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="tokens",
        on_delete=models.CASCADE,
    )
    consumer = models.ForeignKey(Consumer, on_delete=models.CASCADE)

    callback = models.CharField(max_length=255, null=True, blank=True)
    callback_confirmed = models.BooleanField(default=False)

    objects = TokenManager()

    def __unicode__(self):
        return f"{self.get_token_type_display()} Token {self.key} for {self.consumer}"

    def to_string(self, only_key=False):
        token_dict = {
            "oauth_token": self.key,
            "oauth_token_secret": self.secret,
            "oauth_callback_confirmed": "true",
        }

        if self.verifier:
            token_dict.update({"oauth_verifier": self.verifier})

        if only_key:
            del token_dict["oauth_token_secret"]

        return urlencode(token_dict)

    def generate_random_codes(self):
        key = make_random_password(length=KEY_SIZE)
        secret = generate_random(SECRET_SIZE)

        while Token.objects.filter(
            key__exact=key, secret__exact=secret
        ).count():
            secret = generate_random(SECRET_SIZE)

        self.key = key
        self.secret = secret
        self.save()

    # -- OAuth 1.0a stuff

    def get_callback_url(self):
        if self.callback and self.verifier:
            # Append the oauth_verifier.
            parts = urlparse(self.callback)
            scheme, netloc, path, params, query, fragment = parts[:6]
            if query:
                query = f"{query}&oauth_verifier={self.verifier}"
            else:
                query = f"oauth_verifier={self.verifier}"
            return urlunparse((scheme, netloc, path, params, query, fragment))
        return self.callback

    def set_callback(self, callback):
        if callback != "oob":  # out of band, says "we can't do this!"
            self.callback = callback
            self.callback_confirmed = True
            self.save()

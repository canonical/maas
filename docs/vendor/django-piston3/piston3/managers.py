from django.db import models

from .utils import make_random_password

KEY_SIZE = 18
SECRET_SIZE = 32


class KeyManager(models.Manager):
    """Add support for random key/secret generation"""

    def generate_random_codes(self):
        key = make_random_password(length=KEY_SIZE)
        secret = make_random_password(length=SECRET_SIZE)

        while self.filter(key__exact=key, secret__exact=secret).count():
            secret = make_random_password(length=SECRET_SIZE)

        return key, secret


class ConsumerManager(KeyManager):
    def create_consumer(self, name, description=None, user=None):
        """
        Shortcut to create a consumer with random key/secret.
        """
        consumer, created = self.get_or_create(name=name)

        if user:
            consumer.user = user

        if description:
            consumer.description = description

        if created:
            consumer.key, consumer.secret = self.generate_random_codes()
            consumer.save()

        return consumer

    _default_consumer = None


class ResourceManager(models.Manager):
    _default_resource = None

    def get_default_resource(self, name):
        """
        Add cache if you use a default resource.
        """
        if not self._default_resource:
            self._default_resource = self.get(name=name)

        return self._default_resource


class TokenManager(KeyManager):
    def create_token(self, consumer, token_type, timestamp, user=None):
        """
        Shortcut to create a token with random key/secret.
        """
        token, created = self.get_or_create(
            consumer=consumer,
            token_type=token_type,
            timestamp=timestamp,
            user=user,
        )

        if created:
            token.key, token.secret = self.generate_random_codes()
            token.save()

        return token

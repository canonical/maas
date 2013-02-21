# flake8: noqa
# Extract of Django 1.4's forms/fields.py file with modified imports.
from django.core import validators
from django.forms.fields import CharField
from maasserver.dj14.ipv6 import clean_ipv6_address
from maasserver.dj14.validators import ip_address_validators


class GenericIPAddressFormField(CharField):
    default_error_messages = {}

    def __init__(self, protocol='both', unpack_ipv4=False, *args, **kwargs):
        self.unpack_ipv4 = unpack_ipv4
        self.default_validators, invalid_error_message = \
            ip_address_validators(protocol, unpack_ipv4)
        self.default_error_messages['invalid'] = invalid_error_message
        super(GenericIPAddressFormField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if value in validators.EMPTY_VALUES:
            return u''
        if value and ':' in value:
                return clean_ipv6_address(value,
                    self.unpack_ipv4, self.error_messages['invalid'])
        return value

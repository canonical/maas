# flake8: noqa
# Extract of Django 1.4's db/models/fields/__init__.py file with modified
# imports.
from django.core import exceptions
from django.db.models.fields import Field
from django.utils.translation import ugettext_lazy as _
from maasserver.dj14.forms import GenericIPAddressFormField
from maasserver.dj14.ipv6 import clean_ipv6_address
from maasserver.dj14.validators import ip_address_validators


class GenericIPAddressField(Field):
    empty_strings_allowed = True
    description = _("IP address")
    default_error_messages = {}

    def __init__(self, protocol='both', unpack_ipv4=False, *args, **kwargs):
        self.unpack_ipv4 = unpack_ipv4
        self.default_validators, invalid_error_message = \
            ip_address_validators(protocol, unpack_ipv4)
        self.default_error_messages['invalid'] = invalid_error_message
        kwargs['max_length'] = 39
        Field.__init__(self, *args, **kwargs)

    def get_internal_type(self):
        return "GenericIPAddressField"

    def to_python(self, value):
        if value and ':' in value:
            return clean_ipv6_address(value,
                self.unpack_ipv4, self.error_messages['invalid'])
        return value

    def get_db_prep_value(self, value, connection, prepared=False):
        if not prepared:
            value = self.get_prep_value(value)
        return value or None

    def get_prep_value(self, value):
        if value and ':' in value:
            try:
                return clean_ipv6_address(value, self.unpack_ipv4)
            except exceptions.ValidationError:
                pass
        return value

    def formfield(self, **kwargs):
        defaults = {'form_class': GenericIPAddressFormField}
        defaults.update(kwargs)
        return super(GenericIPAddressField, self).formfield(**defaults)

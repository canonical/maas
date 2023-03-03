# This module holds custom fields used in migrations. These can be copies or
# older versions of the ones in actual code, but need to be kept separate so
# that modifications to code doesn't break previous migrations.

from copy import deepcopy
import json

from django.db.models import BinaryField, Field


class EditableBinaryField(BinaryField):
    """An editable binary field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.editable = True

    def deconstruct(self):
        # Override deconstruct not to fail on the removal of the 'editable'
        # field: the Django migration module assumes the field has its default
        # value (False).
        return Field.deconstruct(self)


class JSONObjectField(Field):
    """A field that will store any jsonizable python object."""

    def to_python(self, value):
        """db -> python: json load."""
        assert not isinstance(value, bytes)
        if value is not None:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except ValueError:
                    pass
            return value
        else:
            return None

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def get_db_prep_value(self, value, connection=None, prepared=False):
        """python -> db: json dump.

        Keys are sorted when dumped to guarantee stable output. DB field can
        guarantee uniqueness and be queried (the same dict makes the same
        JSON).
        """
        if value is not None:
            return json.dumps(deepcopy(value), sort_keys=True)
        else:
            return None

    def get_internal_type(self):
        return "TextField"

    def formfield(self, form_class=None, **kwargs):
        """Return a plain `forms.Field` here to avoid "helpful" conversions.

        Django's base model field defaults to returning a `CharField`, which
        means that anything that's not character data gets smooshed to text by
        `CharField.to_python` in forms (via the woefully named `smart_str`).
        This is not helpful.
        """
        if form_class is None:
            form_class = forms.Field
        return super().formfield(form_class=form_class, **kwargs)


class MACAddressField(Field):
    """Model for MAC addresses."""

    def db_type(self, *args, **kwargs):
        return "macaddr"

    def get_prep_value(self, value):
        return super().get_prep_value(value) or None

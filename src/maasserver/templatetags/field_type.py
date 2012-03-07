# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Field type template tag."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
        "field_type"
    ]

from django import template

register = template.Library()

@register.filter('field_type')
def field_type(field):
    return field.field.widget.__class__.__name__

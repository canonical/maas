# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Field type template tag."""


from django import template

register = template.Library()


@register.filter("field_type")
def field_type(field):
    return field.field.widget.__class__.__name__

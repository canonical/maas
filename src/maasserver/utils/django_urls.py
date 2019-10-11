# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django 1.8 compatible imports for URL resolver functions."""

__all__ = [
    "get_callable",
    "get_resolver",
    "get_script_prefix",
    "reverse",
    "set_script_prefix",
    "RegexURLPattern",
    "RegexURLResolver",
]

try:
    from django.urls import (
        get_callable,
        get_resolver,
        get_script_prefix,
        reverse,
        set_script_prefix,
    )
except ImportError:
    from django.core.urlresolvers import (
        get_callable,
        get_resolver,
        get_script_prefix,
        reverse,
        set_script_prefix,
    )

try:
    from django.urls.resolvers import RegexURLPattern, RegexURLResolver
except ImportError:
    from django.core.urlresolvers import RegexURLPattern, RegexURLResolver

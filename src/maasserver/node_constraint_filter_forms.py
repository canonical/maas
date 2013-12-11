# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'AcquireNodeForm',
    ]


import itertools
from itertools import chain
import re

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from maasserver.enum import (
    ARCHITECTURE_CHOICES,
    ARCHITECTURE_CHOICES_DICT,
    )
from maasserver.fields import mac_validator
from maasserver.forms import (
    UnconstrainedMultipleChoiceField,
    ValidatorMultipleChoiceField,
    )
from maasserver.models import (
    Tag,
    Zone,
    )
from maasserver.utils.orm import (
    macs_contain,
    macs_do_not_contain,
    )


def generate_architecture_wildcards(choices=ARCHITECTURE_CHOICES):
    """Map 'primary' architecture names to a list of full expansions.

    Return a dictionary keyed by the primary architecture name (the part before
    the '/'). The value of an entry is a frozenset of full architecture names
    ('primary_arch/subarch') under the keyed primary architecture.
    """
    sorted_arch_list = sorted(choice[0] for choice in choices)

    def extract_primary_arch(arch):
        return arch.split('/')[0]

    return {
        primary_arch: frozenset(subarch_generator)
        for primary_arch, subarch_generator in itertools.groupby(
            sorted_arch_list, key=extract_primary_arch
        )
    }

architecture_wildcards = generate_architecture_wildcards()


# juju uses a general "arm" architecture constraint across all of its
# providers. Since armhf is the cross-distro agreed Linux userspace
# architecture and ABI and ARM servers are expected to only use armhf,
# interpret "arm" to mean "armhf" in MAAS.
architecture_wildcards['arm'] = architecture_wildcards['armhf']


def parse_legacy_tags(values):
    # Support old-method to pass a list of strings using a
    # comma-separated or space-separated list.
    # 'values' is assumed to be a list of strings.
    result = chain.from_iterable(
        re.findall(r'[^\s,]+', value) for value in values)
    return list(result)


# Mapping used to rename the fields from the AcquireNodeForm form.
# The new names correspond to the names used by Juju.  This is used so
# that the search form present on the node listing page can be used to
# filter nodes using Juju's semantics.
JUJU_ACQUIRE_FORM_FIELDS_MAPPING = {
    'name': 'maas-name',
    'tags': 'maas-tags',
    'arch': 'architecture',
    'cpu_count': 'cpu',
}


class RenamableFieldsForm(forms.Form):

    def __init__(self, *args, **kwargs):
        super(RenamableFieldsForm, self).__init__(*args, **kwargs)
        self.field_mapping = {name: name for name in self.fields}

    def get_field_name(self, name):
        """Get the new name of the field named 'name'."""
        return self.field_mapping[name]

    def rename_fields(self, mapping):
        """Rename all the field as described in the given mapping."""
        for old_name, new_name in mapping.items():
            self.rename_field(old_name, new_name)

    def rename_field(self, old_name, new_name):
        """Rename a field."""
        if old_name in self.fields:
            # Rename field mapping.
            self.field_mapping[old_name] = new_name

            # Rename field.
            self.fields[new_name] = self.fields.pop(old_name)

            # Rename clean_field() method if it exists.
            clean_name = "clean_%s" % old_name
            method = getattr(self, clean_name, None)
            if method is not None:
                setattr(self, "clean_%s" % new_name, method)


class AcquireNodeForm(RenamableFieldsForm):
    """A form handling the constraints used to acquire a node."""

    name = forms.CharField(label="Host name", required=False)

    arch = forms.CharField(label="Architecture", required=False)

    cpu_count = forms.FloatField(
        label="CPU count", required=False,
        error_messages={'invalid': "Invalid CPU count: number required."})

    mem = forms.FloatField(
        label="Memory", required=False,
        error_messages={'invalid': "Invalid memory: number of MB required."})

    tags = UnconstrainedMultipleChoiceField(label="Tags", required=False)

    connected_to = ValidatorMultipleChoiceField(
        validator=mac_validator, label="Connected to", required=False,
        error_messages={
            'invalid_list':
            "Invalid parameter: list of MAC addresses required."})

    not_connected_to = ValidatorMultipleChoiceField(
        validator=mac_validator, label="Not connected to", required=False,
        error_messages={
            'invalid_list':
            "Invalid parameter: list of MAC addresses required."})

    zone = forms.CharField(label="Availability zone", required=False)

    ignore_unknown_constraints = True

    @classmethod
    def Strict(cls, *args, **kwargs):
        """A stricter version of the form which rejects unknown parameters."""
        form = cls(*args, **kwargs)
        form.ignore_unknown_constraints = False
        return form

    def clean_arch(self):
        value = self.cleaned_data[self.get_field_name('arch')]
        if value:
            if value in ARCHITECTURE_CHOICES_DICT:
                # Full 'arch/subarch' specified directly.
                return [value]
            elif value in architecture_wildcards:
                # Try to expand 'arch' to all available 'arch/subarch'
                # matches.
                return architecture_wildcards[value]
            raise ValidationError(
                {self.get_field_name('arch'):
                    ['Architecture not recognised.']})
        return None

    def clean_tags(self):
        value = self.cleaned_data[self.get_field_name('tags')]
        if value:
            tag_names = parse_legacy_tags(value)
            # Validate tags.
            tag_names = set(tag_names)
            db_tag_names = set(Tag.objects.filter(
                name__in=tag_names).values_list('name', flat=True))
            if len(tag_names) != len(db_tag_names):
                unknown_tags = tag_names.difference(db_tag_names)
                error_msg = 'No such tag(s): %s.' % ', '.join(
                    "'%s'" % tag for tag in unknown_tags)
                raise ValidationError(
                    {self.get_field_name('arch'): [error_msg]})
            return tag_names
        return None

    def clean_zone(self):
        value = self.cleaned_data[self.get_field_name('zone')]
        if value:
            zone_names = Zone.objects.all().values_list('name', flat=True)
            if value not in zone_names:
                error_msg = "No such zone: '%s'." % value
                raise ValidationError(
                    {self.get_field_name('zone'): [error_msg]})
            return value
        return None

    def clean(self):
        if not self.ignore_unknown_constraints:
            unknown_constraints = set(
                self.data).difference(set(self.field_mapping.values()))
            for constraint in unknown_constraints:
                msg = "No such constraint."
                self._errors[constraint] = self.error_class([msg])
        return super(AcquireNodeForm, self).clean()

    def filter_nodes(self, nodes):
        filtered_nodes = nodes

        # Filter by hostname.
        hostname = self.cleaned_data.get(self.get_field_name('name'))
        if hostname:
            clause = Q(hostname=hostname)
            # If the given hostname has a domain part, try matching
            # against the nodes' FQDNs as well (the FQDN is built using
            # the nodegroup's name as the domain name).
            if "." in hostname:
                host, domain = hostname.split('.', 1)
                hostname_clause = (
                    Q(hostname__startswith="%s." % host) |
                    Q(hostname=host)
                )
                domain_clause = Q(nodegroup__name=domain)
                clause = clause | (hostname_clause & domain_clause)
            filtered_nodes = filtered_nodes.filter(clause)

        # Filter by architecture.
        arch = self.cleaned_data.get(self.get_field_name('arch'))
        if arch:
            filtered_nodes = filtered_nodes.filter(architecture__in=arch)

        # Filter by cpu_count.
        cpu_count = self.cleaned_data.get(self.get_field_name('cpu_count'))
        if cpu_count:
            filtered_nodes = filtered_nodes.filter(cpu_count__gte=cpu_count)

        # Filter by memory.
        mem = self.cleaned_data.get(self.get_field_name('mem'))
        if mem:
            filtered_nodes = filtered_nodes.filter(memory__gte=mem)

        # Filter by tags.
        tags = self.cleaned_data.get(self.get_field_name('tags'))
        if tags:
            for tag in tags:
                filtered_nodes = filtered_nodes.filter(tags__name=tag)

        # Filter by zone.
        zone = self.cleaned_data.get(self.get_field_name('zone'))
        if zone:
            filtered_nodes = filtered_nodes.filter(zone=zone)

        # Filter by connected_to.
        connected_to = self.cleaned_data.get(
            self.get_field_name('connected_to'))
        if connected_to:
            where, params = macs_contain(
                "routers", connected_to)
            filtered_nodes = filtered_nodes.extra(
                where=[where], params=params)

        # Filter by not_connected_to.
        not_connected_to = self.cleaned_data.get(
            self.get_field_name('not_connected_to'))
        if not_connected_to:
            where, params = macs_do_not_contain(
                "routers", not_connected_to)
            filtered_nodes = filtered_nodes.extra(
                where=[where], params=params)

        return filtered_nodes

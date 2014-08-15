# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tables to help with naming."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'CandidateName',
    'gen_candidate_names',
    ]

from itertools import (
    imap,
    product,
    )
from random import shuffle

from django.db.models import (
    IntegerField,
    Model,
    SlugField,
    )
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave


class CandidateName(CleanSave, Model):
    """A `CandidateName` represents a name we can use to name something."""

    name = SlugField(blank=False, null=False)
    position = IntegerField(
        blank=False, null=False,
        choices=((1, "Adjective"), (2, "Noun")),
        help_text=(
            "Position specifies where in an automatically generated name "
            "this row's name ought to go. For example, if you always mark "
            "adjectives with position 1 and nouns with position 2, then "
            "your naming scheme will be adjective-noun."
        ))

    class Meta(DefaultMeta):
        verbose_name = "Candidate name"
        verbose_name_plural = "Candidate names"
        unique_together = "name", "position"

    def __unicode__(self):
        return "CandidateName (%s, in position %d)" % (
            self.name, self.position)


def shuffled(iterable):
    items = list(iterable)
    shuffle(items)
    return items


def get_distinct_positions():
    return CandidateName.objects.distinct(
        "position").order_by("position").values_list("position", flat=True)


def get_names_for_position(position):
    return CandidateName.objects.filter(
        position=position).values_list("name", flat=True)


def gen_candidate_names(sep="-"):
    """Generate candidate ``adjective-noun``-like names.

    Out of the box this will return 1276939 different names.

    While not slow, there is some initial overhead when calling this function.
    Use the generator instead of calling this function repeatedly, because
    there's almost no overhead to pulling names from the generator.
    """
    # Slurp in all names for all position because it's quick.
    position_names = imap(get_names_for_position, get_distinct_positions())
    # Shuffling a list of 1000 elements is fairly quick (~250usec here).
    return imap(sep.join, product(*imap(shuffled, position_names)))

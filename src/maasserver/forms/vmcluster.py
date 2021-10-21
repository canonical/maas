# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""VMCluster forms."""

from django import forms
from django.forms import BooleanField


class DeleteVMClusterForm(forms.Form):
    """Delete VMCluster"""

    decompose = BooleanField(required=False, initial=False)

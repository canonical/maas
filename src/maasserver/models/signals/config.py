# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Signals called when config values changed."""

from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def dns_kms_setting_changed(sender, instance, created, **kwargs):
    from maasserver.models.domain import dns_kms_setting_changed

    dns_kms_setting_changed()


# Changes to windows_kms_host.
signals.watch_config(dns_kms_setting_changed, "windows_kms_host")


# Enable all signals by default.
signals.enable()

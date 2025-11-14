# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to Domain changes."""

from django.db.models.signals import post_delete, post_save

from maascommon.enums.dns import DnsUpdateAction
from maasserver.models import DNSPublication, Domain
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def post_created_dns_publication(sender, instance, created, **kwargs):
    if created and instance.authoritative:
        DNSPublication.objects.create_for_config_update(
            source=f"added zone {instance.name}",
            action=DnsUpdateAction.RELOAD,
        )


def post_delete_dns_publication(sender, instance, **kwargs):
    if instance.authoritative:
        DNSPublication.objects.create_for_config_update(
            source=f"removed zone {instance.name}",
            action=DnsUpdateAction.RELOAD,
        )


def updated_fields(instance, old_values, **kwargs):
    [old_authoritative, old_ttl, old_name] = old_values

    if old_authoritative and not instance.authoritative:
        # No longer authoritative, remove zone
        DNSPublication.objects.create_for_config_update(
            source=f"removed zone {old_name}",
            action=DnsUpdateAction.RELOAD,
        )
    elif not old_authoritative and instance.authoritative:
        # Now authoritative, add zone
        DNSPublication.objects.create_for_config_update(
            source=f"added zone {instance.name}",
            action=DnsUpdateAction.RELOAD,
        )
    elif old_authoritative and instance.authoritative:
        changes = []
        if old_name != instance.name:
            changes.append(f"renamed zone from {old_name} to {instance.name}")
        if old_ttl != instance.ttl:
            changes.append(f"changed TTL from {old_ttl} to {instance.ttl}")
        if changes:
            DNSPublication.objects.create_for_config_update(
                source=f"zone {instance.name} {', '.join(changes)}",
                action=DnsUpdateAction.RELOAD,
            )


signals.watch(post_save, post_created_dns_publication, sender=Domain)
signals.watch(post_delete, post_delete_dns_publication, sender=Domain)
signals.watch_fields(
    updated_fields, Domain, ["authoritative", "ttl", "name"], delete=False
)

# Enable all signals by default.
signals.enable()

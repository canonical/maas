# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to DNSData changes."""

from django.db.models.signals import post_delete, post_save

from maascommon.enums.dns import DnsUpdateAction
from maasserver.models import DNSData, DNSPublication
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def post_save_dns_publication(sender, instance, created, **kwargs):
    domain_name = instance.dnsresource.domain.name
    if created:
        update = f"added {instance.rrtype} to resource {instance.dnsresource.name} on zone {domain_name}"
    else:
        update = f"updated {instance.rrtype} in resource {instance.dnsresource.name} on zone {domain_name}"
    DNSPublication.objects.create_for_config_update(
        source=update,
        action=DnsUpdateAction.RELOAD,
    )


def post_delete_dns_publication(sender, instance, **kwargs):
    domain_name = instance.dnsresource.domain.name
    DNSPublication.objects.create_for_config_update(
        source=f"removed {instance.rrtype} from resource {instance.dnsresource.name} on zone {domain_name}",
        action=DnsUpdateAction.RELOAD,
    )


signals.watch(post_save, post_save_dns_publication, sender=DNSData)
signals.watch(post_delete, post_delete_dns_publication, sender=DNSData)

# Enable all signals by default.
signals.enable()

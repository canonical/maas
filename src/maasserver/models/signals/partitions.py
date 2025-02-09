# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to partition changes."""

from django.db.models.signals import post_delete

from maasserver.models.partition import Partition
from maasserver.models.partitiontable import PartitionTable
from maasserver.utils.signals import SignalsManager

signals = SignalsManager()


def delete_partition_table(sender, instance, **kwargs):
    """Delete the partition table if this is the last partition on the
    partition table."""
    try:
        partition_table = instance.partition_table
    except PartitionTable.DoesNotExist:
        pass  # Nothing to do.
    else:
        if not partition_table.partitions.exists():
            partition_table.delete()


signals.watch(post_delete, delete_partition_table, Partition)


# Enable all signals by default.
signals.enable()

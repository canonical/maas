"""A machine handler that uses sqlalchemy ORM.

It uses as much of the ORM features as posible, where possible.
That is, unless there's a very big performance penality, it gets
the whole objects, rather than trying to get only the specific
data.

The object class declarations could be simplified by re-using
the table definintions from maasspike.sqlalchemy_core, but they
are completely redefined here to show how a non-hybrid declaration
would look like.
"""

import typing

from sqlalchemy import Column, ForeignKey, select, String, Table
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import (
    DeclarativeBase,
    joinedload,
    Mapped,
    mapped_column,
    relationship,
    selectin_polymorphic,
    selectinload,
)
from sqlalchemy.sql.expression import func

from maasserver.enum import NODE_TYPE, NODE_TYPE_CHOICES_DICT

# Copied from maasserver.websocket.handlers.node
NODE_TYPE_TO_LINK_TYPE = {
    NODE_TYPE.DEVICE: "device",
    NODE_TYPE.MACHINE: "machine",
    NODE_TYPE.RACK_CONTROLLER: "controller",
    NODE_TYPE.REGION_CONTROLLER: "controller",
    NODE_TYPE.REGION_AND_RACK_CONTROLLER: "controller",
}


class Base(DeclarativeBase):
    pass


NodeTag = Table(
    "maasserver_node_tags",
    Base.metadata,
    Column("id", primary_key=True),
    Column("tag_id", ForeignKey("maasserver_tag.id")),
    Column("node_id", ForeignKey("maasserver_node.id")),
)


class Machine(Base):
    __tablename__ = "maasserver_node"
    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str]
    system_id: Mapped[str]
    node_type: Mapped[int]
    cpu_count: Mapped[int]
    memory: Mapped[int]
    description: Mapped[str]
    error_description: Mapped[str]
    power_state: Mapped[str]
    locked: Mapped[bool]
    domain_id: Mapped[int] = mapped_column(ForeignKey("maasserver_domain.id"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("auth_user.id"))
    parent_id: Mapped[int] = mapped_column(ForeignKey("maasserver_node.id"))
    pool_id: Mapped[int] = mapped_column(
        ForeignKey("maasserver_resourcepool.id")
    )
    zone_id: Mapped[int] = mapped_column(ForeignKey("maasserver_zone.id"))
    current_config_id: Mapped[int] = mapped_column(
        ForeignKey("maasserver_nodeconfig.id")
    )

    owner: Mapped["User"] = relationship(lazy="raise")
    domain: Mapped["Domain"] = relationship(lazy="raise")
    pool: Mapped["ResourcePool"] = relationship(lazy="raise")
    zone: Mapped["Zone"] = relationship(lazy="raise")
    parent: Mapped["Machine"] = relationship(lazy="raise")
    tags: Mapped[list["Tag"]] = relationship(lazy="raise", secondary=NodeTag)
    current_config: Mapped["NodeConfig"] = relationship(
        lazy="raise", foreign_keys="NodeConfig.node_id"
    )


class Domain(Base):
    __tablename__ = "maasserver_domain"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class User(Base):
    __tablename__ = "auth_user"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]


class ResourcePool(Base):
    __tablename__ = "maasserver_resourcepool"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class Zone(Base):
    __tablename__ = "maasserver_zone"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


class Tag(Base):
    __tablename__ = "maasserver_tag"
    id: Mapped[int] = mapped_column(primary_key=True)


class NodeConfig(Base):
    __tablename__ = "maasserver_nodeconfig"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    node_id: Mapped[int] = mapped_column(ForeignKey("maasserver_node.id"))

    block_devices: Mapped[typing.List["BlockDevice"]] = relationship(
        lazy="raise", back_populates="node_config"
    )


class BlockDevice(Base):
    __tablename__ = "maasserver_blockdevice"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    device_type: Mapped[str]
    size: Mapped[int]
    node_config_id: Mapped[int] = mapped_column(
        ForeignKey("maasserver_nodeconfig.id")
    )
    tags: Mapped[typing.List[str]] = mapped_column(postgresql.ARRAY(String))

    node_config: Mapped["NodeConfig"] = relationship(
        lazy="raise", back_populates="block_devices"
    )
    partition_tables: Mapped[typing.List["PartitionTable"]] = relationship(
        lazy="raise", back_populates="block_device"
    )
    __mapper_args__ = {
        "polymorphic_identity": "generic",
        "polymorphic_on": "device_type",
    }


class PhysicalBlockDevice(BlockDevice):
    __tablename__ = "maasserver_physicalblockdevice"
    blockdevice_ptr_id: Mapped[int] = mapped_column(
        ForeignKey("maasserver_blockdevice.id"),
        primary_key=True,
    )
    __mapper_args__ = {"polymorphic_identity": "physical"}


class VirtualBlockDevice(BlockDevice):
    __tablename__ = "maasserver_virtualblockdevice"
    blockdevice_ptr_id: Mapped[int] = mapped_column(
        ForeignKey("maasserver_blockdevice.id"),
        primary_key=True,
    )
    __mapper_args__ = {"polymorphic_identity": "virtual"}


class PartitionTable(Base):
    __tablename__ = "maasserver_partitiontable"
    id: Mapped[int] = mapped_column(primary_key=True)
    block_device_id: Mapped[int] = mapped_column(
        ForeignKey("maasserver_blockdevice.id")
    )

    block_device: Mapped["BlockDevice"] = relationship(
        lazy="raise", back_populates="partition_tables"
    )
    partitions: Mapped[typing.List["Partition"]] = relationship(
        lazy="raise", back_populates="partition_table"
    )


class Partition(Base):
    __tablename__ = "maasserver_partition"
    id: Mapped[int] = mapped_column(primary_key=True)
    partition_table_id: Mapped[int] = mapped_column(
        ForeignKey("maasserver_partitiontable.id")
    )
    tags: Mapped[typing.List[str]] = mapped_column(postgresql.ARRAY(String))

    partition_table: Mapped["PartitionTable"] = relationship(
        lazy="raise", back_populates="partitions"
    )


def get_all_storage_tags(blockdevices):
    """Copy of NodeHandler.get_all_storage_tags().

    It has been modified to work with sqlalchemy objects.
    """

    tags = set()
    for blockdevice in blockdevices:
        tags = tags.union(blockdevice.tags)
        partition_table = (
            blockdevice.partition_tables[0]
            if blockdevice.partition_tables
            else None
        )
        if partition_table is not None:
            for partition in partition_table.partitions:
                tags = tags.union(partition.tags)
    return tags


def list_machines(session, admin, limit=None):
    storage_query = (
        select(
            Machine.id,
            func.count(PhysicalBlockDevice.blockdevice_ptr_id).label(
                "disk_count"
            ),
            func.sum(func.coalesce(PhysicalBlockDevice.size, 0)).label(
                "storage"
            ),
        )
        .select_from(PhysicalBlockDevice)
        .join(NodeConfig, NodeConfig.id == PhysicalBlockDevice.node_config_id)
        .join(Machine, Machine.id == NodeConfig.node_id)
        .group_by(Machine.id)
    ).cte()
    rows = session.execute(
        select(
            Machine,
            storage_query.c.disk_count,
            func.round((storage_query.c.storage / 1000**3), 1).label(
                "storage"
            ),
        )
        .options(
            joinedload(Machine.domain),
            joinedload(Machine.owner),
            joinedload(Machine.pool),
            joinedload(Machine.zone),
            joinedload(Machine.parent),
            selectin_polymorphic(BlockDevice, [PhysicalBlockDevice]),
            joinedload(Machine.current_config)
            .selectinload(NodeConfig.block_devices)
            .selectinload(BlockDevice.partition_tables)
            .selectinload(PartitionTable.partitions),
            selectinload(Machine.tags),
        )
        .join(storage_query, storage_query.c.id == Machine.id)
        .where(Machine.node_type == NODE_TYPE.MACHINE)
        .order_by(Machine.id)
        .limit(limit)
    )
    result = []
    for machine, disk_count, storage in rows:
        result.append(
            {
                "id": machine.id,
                "system_id": machine.system_id,
                "hostname": machine.hostname,
                "cpu_count": machine.cpu_count,
                "memory": machine.memory,
                "description": machine.description,
                "error_description": machine.error_description,
                "power_state": machine.power_state,
                "locked": machine.locked,
                "domain": {
                    "id": machine.domain.id,
                    "name": machine.domain.name,
                },
                "pool": {"id": machine.pool.id, "name": machine.pool.name},
                "zone": {"id": machine.zone.id, "name": machine.zone.name},
                "fqdn": f"{machine.hostname}.{machine.domain.name}",
                "owner": machine.owner.username if machine.owner else "",
                "parent": machine.parent.system_id if machine.parent else None,
                # XXX: Need better permission check.
                "permissions": ["edit", "delete"]
                if admin.is_superuser
                else None,
                "node_type_display": NODE_TYPE_CHOICES_DICT[machine.node_type],
                "link_type": NODE_TYPE_TO_LINK_TYPE[machine.node_type],
                "tags": [tag.id for tag in machine.tags],
                "physical_disk_count": disk_count,
                "storage": storage,
                "storage_tags": get_all_storage_tags(
                    machine.current_config.block_devices
                ),
            }
        )
    return result

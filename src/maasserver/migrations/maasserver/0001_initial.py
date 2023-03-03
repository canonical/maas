from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion

import maasserver.fields
import maasserver.migrations.fields
import maasserver.models.bootresource
import maasserver.models.cleansave
import maasserver.models.fabric
import maasserver.models.filestorage
import maasserver.models.interface
import maasserver.models.node
import maasserver.models.space
import maasserver.models.sshkey
import maasserver.models.sslkey
import maasserver.models.subnet
import maasserver.utils.dns
import metadataserver.fields


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("piston3", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockDevice",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        help_text="Name of block device. (e.g. sda)",
                        max_length=255,
                    ),
                ),
                (
                    "id_path",
                    models.FilePathField(
                        help_text="Path of by-id alias. (e.g. /dev/disk/by-id/wwn-0x50004...)",
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "size",
                    models.BigIntegerField(
                        help_text="Size of block device in bytes.",
                        validators=[
                            django.core.validators.MinValueValidator(4194304)
                        ],
                    ),
                ),
                (
                    "block_size",
                    models.IntegerField(
                        help_text="Size of a block on the device in bytes.",
                        validators=[
                            django.core.validators.MinValueValidator(512)
                        ],
                    ),
                ),
                (
                    "tags",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        base_field=models.TextField(),
                        null=True,
                        blank=True,
                        default=list,
                    ),
                ),
            ],
            options={"ordering": ["id"]},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="BootResource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "rtype",
                    models.IntegerField(
                        editable=False,
                        choices=[
                            (0, "Synced"),
                            (1, "Generated"),
                            (2, "Uploaded"),
                        ],
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "architecture",
                    models.CharField(
                        max_length=255,
                        validators=[
                            maasserver.models.bootresource.validate_architecture
                        ],
                    ),
                ),
                (
                    "extra",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", editable=False, blank=True
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="BootResourceFile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("filename", models.CharField(max_length=255, editable=False)),
                (
                    "filetype",
                    models.CharField(
                        default="root-tgz",
                        max_length=20,
                        editable=False,
                        choices=[
                            ("root-tgz", "Root Image (tar.gz)"),
                            ("root-dd", "Root Compressed DD (dd -> tar.gz)"),
                            ("root-image.gz", "Compressed Root Image"),
                            ("boot-kernel", "Linux ISCSI Kernel"),
                            ("boot-initrd", "Initial ISCSI Ramdisk"),
                            ("boot-dtb", "ISCSI Device Tree Blob"),
                            ("di-kernel", "Linux DI Kernel"),
                            ("di-initrd", "Initial DI Ramdisk"),
                            ("di-dtb", "DI Device Tree Blob"),
                        ],
                    ),
                ),
                (
                    "extra",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", editable=False, blank=True
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="BootResourceSet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("version", models.CharField(max_length=255, editable=False)),
                ("label", models.CharField(max_length=255, editable=False)),
                (
                    "resource",
                    models.ForeignKey(
                        related_name="sets",
                        editable=False,
                        to="maasserver.BootResource",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="BootSource",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "url",
                    models.URLField(
                        help_text="The URL of the BootSource.", unique=True
                    ),
                ),
                (
                    "keyring_filename",
                    models.FilePathField(
                        help_text="The path to the keyring file for this BootSource.",
                        blank=True,
                    ),
                ),
                (
                    "keyring_data",
                    maasserver.migrations.fields.EditableBinaryField(
                        help_text="The GPG keyring for this BootSource, as a binary blob.",
                        blank=True,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="BootSourceCache",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("os", models.CharField(max_length=20)),
                ("arch", models.CharField(max_length=20)),
                ("subarch", models.CharField(max_length=20)),
                ("release", models.CharField(max_length=20)),
                ("label", models.CharField(max_length=20)),
                (
                    "boot_source",
                    models.ForeignKey(
                        to="maasserver.BootSource", on_delete=models.CASCADE
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="BootSourceSelection",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "os",
                    models.CharField(
                        default="",
                        help_text="The operating system for which to import resources.",
                        max_length=20,
                        blank=True,
                    ),
                ),
                (
                    "release",
                    models.CharField(
                        default="",
                        help_text="The OS release for which to import resources.",
                        max_length=20,
                        blank=True,
                    ),
                ),
                (
                    "arches",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        base_field=models.TextField(),
                        null=True,
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "subarches",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        base_field=models.TextField(),
                        null=True,
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "labels",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        base_field=models.TextField(),
                        null=True,
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "boot_source",
                    models.ForeignKey(
                        to="maasserver.BootSource", on_delete=models.CASCADE
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="CacheSet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="CandidateName",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.SlugField()),
                (
                    "position",
                    models.IntegerField(
                        help_text="Position specifies where in an automatically generated name this row's name ought to go. For example, if you always mark adjectives with position 1 and nouns with position 2, then your naming scheme will be adjective-noun.",
                        choices=[(1, "Adjective"), (2, "Noun")],
                    ),
                ),
            ],
            options={
                "verbose_name": "Candidate name",
                "verbose_name_plural": "Candidate names",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="ComponentError",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("component", models.CharField(unique=True, max_length=40)),
                ("error", models.CharField(max_length=1000)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Config",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("name", models.CharField(unique=True, max_length=255)),
                (
                    "value",
                    maasserver.migrations.fields.JSONObjectField(null=True),
                ),
            ],
        ),
        migrations.CreateModel(
            name="DownloadProgress",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("filename", models.CharField(max_length=255, editable=False)),
                ("size", models.IntegerField(blank=True, null=True)),
                (
                    "bytes_downloaded",
                    models.IntegerField(blank=True, null=True),
                ),
                ("error", models.CharField(max_length=1000, blank=True)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Event",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "action",
                    models.TextField(default="", editable=False, blank=True),
                ),
                (
                    "description",
                    models.TextField(default="", editable=False, blank=True),
                ),
            ],
            options={"verbose_name": "Event record"},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="EventType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        unique=True, max_length=255, editable=False
                    ),
                ),
                (
                    "description",
                    models.CharField(max_length=255, editable=False),
                ),
                ("level", models.IntegerField(editable=False, db_index=True)),
            ],
            options={"verbose_name": "Event type"},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Fabric",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        blank=True,
                        max_length=256,
                        null=True,
                        validators=[
                            maasserver.models.fabric.validate_fabric_name
                        ],
                    ),
                ),
                (
                    "class_type",
                    models.CharField(
                        blank=True,
                        max_length=256,
                        null=True,
                        validators=[
                            django.core.validators.RegexValidator("^[ \\w-]+$")
                        ],
                    ),
                ),
            ],
            options={
                "verbose_name": "Fabric",
                "verbose_name_plural": "Fabrics",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="FanNetwork",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        help_text="Name of the fan network",
                        unique=True,
                        max_length=256,
                        validators=[
                            django.core.validators.RegexValidator("^[ \\w-]+$")
                        ],
                    ),
                ),
                ("overlay", maasserver.fields.IPv4CIDRField(unique=True)),
                ("underlay", maasserver.fields.IPv4CIDRField(unique=True)),
                ("dhcp", models.NullBooleanField()),
                (
                    "host_reserve",
                    models.PositiveIntegerField(
                        default=1, null=True, blank=True
                    ),
                ),
                (
                    "bridge",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        null=True,
                        help_text="If specified, this bridge name is used on the hosts",
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[\\w\\-_]+$"
                            )
                        ],
                    ),
                ),
                (
                    "off",
                    models.NullBooleanField(
                        default=False,
                        help_text="Create the configuration, but mark it as 'off'",
                    ),
                ),
            ],
            options={
                "verbose_name": "Fan Network",
                "verbose_name_plural": "Fan Networks",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="FileStorage",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("filename", models.CharField(max_length=255, editable=False)),
                ("content", metadataserver.fields.BinaryField(blank=True)),
                (
                    "key",
                    models.CharField(
                        default=maasserver.models.filestorage.generate_filestorage_key,
                        unique=True,
                        max_length=36,
                        editable=False,
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        default=None,
                        blank=True,
                        editable=False,
                        to=settings.AUTH_USER_MODEL,
                        null=True,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Filesystem",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("uuid", models.CharField(max_length=36, editable=False)),
                (
                    "fstype",
                    models.CharField(
                        default="ext4",
                        max_length=20,
                        choices=[
                            ("ext2", "ext2"),
                            ("ext4", "ext4"),
                            ("xfs", "xfs"),
                            ("fat32", "fat32"),
                            ("vfat", "vfat"),
                            ("lvm-pv", "lvm"),
                            ("raid", "raid"),
                            ("raid-spare", "raid-spare"),
                            ("bcache-cache", "bcache-cache"),
                            ("bcache-backing", "bcache-backing"),
                        ],
                    ),
                ),
                (
                    "label",
                    models.CharField(max_length=255, null=True, blank=True),
                ),
                (
                    "create_params",
                    models.CharField(max_length=255, null=True, blank=True),
                ),
                (
                    "mount_point",
                    models.CharField(max_length=255, null=True, blank=True),
                ),
                (
                    "mount_params",
                    models.CharField(max_length=255, null=True, blank=True),
                ),
                ("acquired", models.BooleanField(default=False)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="FilesystemGroup",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "uuid",
                    models.CharField(
                        unique=True, max_length=36, editable=False
                    ),
                ),
                (
                    "group_type",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("raid-0", "RAID 0"),
                            ("raid-1", "RAID 1"),
                            ("raid-5", "RAID 5"),
                            ("raid-6", "RAID 6"),
                            ("raid-10", "RAID 10"),
                            ("lvm-vg", "LVM VG"),
                            ("bcache", "Bcache"),
                        ],
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "create_params",
                    models.CharField(max_length=255, null=True, blank=True),
                ),
                (
                    "cache_mode",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        null=True,
                        choices=[
                            ("writeback", "Writeback"),
                            ("writethrough", "Writethrough"),
                            ("writearound", "Writearound"),
                        ],
                    ),
                ),
                (
                    "cache_set",
                    models.ForeignKey(
                        blank=True,
                        to="maasserver.CacheSet",
                        null=True,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Interface",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        help_text="Interface name.",
                        max_length=255,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[\\w\\-_.:]+$"
                            )
                        ],
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        max_length=20,
                        editable=False,
                        choices=[
                            ("physical", "Physical interface"),
                            ("bond", "Bond"),
                            ("vlan", "VLAN interface"),
                            ("alias", "Alias"),
                            ("unknown", "Unknown"),
                        ],
                    ),
                ),
                (
                    "mac_address",
                    maasserver.migrations.fields.MACAddressField(
                        null=True, blank=True
                    ),
                ),
                (
                    "ipv4_params",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", blank=True
                    ),
                ),
                (
                    "ipv6_params",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", blank=True
                    ),
                ),
                (
                    "params",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", blank=True
                    ),
                ),
                (
                    "tags",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        base_field=models.TextField(),
                        null=True,
                        blank=True,
                        default=list,
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ("created",),
                "verbose_name": "Interface",
                "verbose_name_plural": "Interfaces",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="InterfaceRelationship",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "child",
                    models.ForeignKey(
                        related_name="parent_relationships",
                        to="maasserver.Interface",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        related_name="children_relationships",
                        to="maasserver.Interface",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={"abstract": False},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="LargeFile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "sha256",
                    models.CharField(
                        unique=True, max_length=64, editable=False
                    ),
                ),
                ("total_size", models.BigIntegerField(editable=False)),
                ("content", maasserver.fields.LargeObjectField()),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="LicenseKey",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                ("osystem", models.CharField(max_length=255)),
                ("distro_series", models.CharField(max_length=255)),
                (
                    "license_key",
                    models.CharField(
                        help_text="License key for operating system",
                        max_length=255,
                        verbose_name="License Key",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Node",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "system_id",
                    models.CharField(
                        default=maasserver.models.node.generate_node_system_id,
                        unique=True,
                        max_length=41,
                        editable=False,
                    ),
                ),
                (
                    "hostname",
                    models.CharField(
                        default="",
                        unique=True,
                        max_length=255,
                        blank=True,
                        validators=[maasserver.utils.dns.validate_hostname],
                    ),
                ),
                (
                    "status",
                    models.IntegerField(
                        default=0,
                        editable=False,
                        choices=[
                            (0, "New"),
                            (1, "Commissioning"),
                            (2, "Failed commissioning"),
                            (3, "Missing"),
                            (4, "Ready"),
                            (5, "Reserved"),
                            (10, "Allocated"),
                            (9, "Deploying"),
                            (6, "Deployed"),
                            (7, "Retired"),
                            (8, "Broken"),
                            (11, "Failed deployment"),
                            (12, "Releasing"),
                            (13, "Releasing failed"),
                            (14, "Disk erasing"),
                            (15, "Failed disk erasing"),
                        ],
                    ),
                ),
                (
                    "bios_boot_method",
                    models.CharField(max_length=31, null=True, blank=True),
                ),
                (
                    "boot_type",
                    models.CharField(
                        default="fastpath",
                        max_length=20,
                        choices=[
                            ("fastpath", "Fastpath Installer"),
                            ("di", "Debian Installer"),
                        ],
                    ),
                ),
                (
                    "osystem",
                    models.CharField(default="", max_length=20, blank=True),
                ),
                (
                    "distro_series",
                    models.CharField(default="", max_length=20, blank=True),
                ),
                (
                    "architecture",
                    models.CharField(max_length=31, null=True, blank=True),
                ),
                (
                    "min_hwe_kernel",
                    models.CharField(max_length=31, null=True, blank=True),
                ),
                (
                    "hwe_kernel",
                    models.CharField(max_length=31, null=True, blank=True),
                ),
                (
                    "installable",
                    models.BooleanField(
                        default=True, db_index=True, editable=False
                    ),
                ),
                (
                    "routers",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        base_field=maasserver.migrations.fields.MACAddressField(),
                        null=True,
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "agent_name",
                    models.CharField(
                        default="", max_length=255, null=True, blank=True
                    ),
                ),
                (
                    "error_description",
                    models.TextField(default="", editable=False, blank=True),
                ),
                ("cpu_count", models.IntegerField(default=0)),
                ("memory", models.IntegerField(default=0)),
                (
                    "swap_size",
                    models.BigIntegerField(
                        default=None, null=True, blank=True
                    ),
                ),
                (
                    "power_type",
                    models.CharField(default="", max_length=10, blank=True),
                ),
                (
                    "power_parameters",
                    maasserver.migrations.fields.JSONObjectField(
                        default="", max_length=32768, blank=True
                    ),
                ),
                (
                    "power_state",
                    models.CharField(
                        default="unknown",
                        max_length=10,
                        editable=False,
                        choices=[
                            ("on", "On"),
                            ("off", "Off"),
                            ("unknown", "Unknown"),
                            ("error", "Error"),
                        ],
                    ),
                ),
                (
                    "power_state_updated",
                    models.DateTimeField(
                        default=None, null=True, editable=False
                    ),
                ),
                (
                    "error",
                    models.CharField(default="", max_length=255, blank=True),
                ),
                ("netboot", models.BooleanField(default=True)),
                (
                    "license_key",
                    models.CharField(max_length=30, null=True, blank=True),
                ),
                (
                    "disable_ipv4",
                    models.BooleanField(
                        default=False,
                        help_text="On operating systems where this choice is supported, this option disables IPv4 networking on this node when it is deployed.  IPv4 may still be used for booting and installing the node.  THIS MAY STOP YOUR NODE FROM WORKING.  Do not disable IPv4 unless you know what you're doing: clusters must be configured to use a MAAS URL with a hostname that resolves on both IPv4 and IPv6.",
                        verbose_name="Disable IPv4 when deployed",
                    ),
                ),
                (
                    "boot_cluster_ip",
                    models.GenericIPAddressField(
                        default=None, null=True, editable=False, blank=True
                    ),
                ),
                ("enable_ssh", models.BooleanField(default=False)),
                ("skip_networking", models.BooleanField(default=False)),
                ("skip_storage", models.BooleanField(default=False)),
                (
                    "boot_interface",
                    models.ForeignKey(
                        related_name="+",
                        on_delete=django.db.models.deletion.SET_NULL,
                        default=None,
                        blank=True,
                        editable=False,
                        to="maasserver.Interface",
                        null=True,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="NodeGroup",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "cluster_name",
                    models.CharField(unique=True, max_length=100, blank=True),
                ),
                (
                    "name",
                    maasserver.fields.DomainNameField(
                        blank=True, max_length=80
                    ),
                ),
                (
                    "status",
                    models.IntegerField(
                        default=1, choices=[(1, "Enabled"), (2, "Disabled")]
                    ),
                ),
                (
                    "api_key",
                    models.CharField(
                        unique=True, max_length=18, editable=False
                    ),
                ),
                (
                    "dhcp_key",
                    models.CharField(
                        default="", max_length=255, editable=False, blank=True
                    ),
                ),
                ("uuid", models.CharField(unique=True, max_length=36)),
                (
                    "maas_url",
                    models.CharField(
                        default="", max_length=255, editable=False, blank=True
                    ),
                ),
                (
                    "default_disable_ipv4",
                    models.BooleanField(
                        default=False,
                        help_text="Default setting for new nodes: disable IPv4 when deploying, on operating systems where this is supported.",
                        verbose_name="Disable IPv4 by default when deploying nodes",
                    ),
                ),
                (
                    "api_token",
                    models.OneToOneField(
                        editable=False,
                        to="piston3.Token",
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="NodeGroupInterface",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "ip",
                    models.GenericIPAddressField(
                        help_text="Static IP Address of the interface",
                        verbose_name="IP",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        default="",
                        help_text="Identifying name for this cluster interface.  Must be unique within the cluster, and consist only of letters, digits, dashes, and colons.",
                        max_length=255,
                        blank=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[\\w:.-]+$"
                            )
                        ],
                    ),
                ),
                (
                    "management",
                    models.IntegerField(
                        default=0,
                        choices=[
                            (0, "Unmanaged"),
                            (1, "DHCP"),
                            (2, "DHCP and DNS"),
                        ],
                    ),
                ),
                (
                    "interface",
                    models.CharField(
                        default="",
                        help_text="Network interface (e.g. 'eth1').",
                        max_length=255,
                        blank=True,
                    ),
                ),
                (
                    "ip_range_low",
                    models.GenericIPAddressField(
                        default=None,
                        blank=True,
                        help_text="Lowest IP number of the range for dynamic IPs, used for enlistment, commissioning and unknown devices.",
                        null=True,
                        verbose_name="DHCP dynamic IP range low value",
                    ),
                ),
                (
                    "ip_range_high",
                    models.GenericIPAddressField(
                        default=None,
                        blank=True,
                        help_text="Highest IP number of the range for dynamic IPs, used for enlistment, commissioning and unknown devices.",
                        null=True,
                        verbose_name="DHCP dynamic IP range high value",
                    ),
                ),
                (
                    "static_ip_range_low",
                    models.GenericIPAddressField(
                        default=None,
                        blank=True,
                        help_text="Lowest IP number of the range for IPs given to allocated nodes, must be in same network as dynamic range.",
                        null=True,
                        verbose_name="Static IP range low value",
                    ),
                ),
                (
                    "static_ip_range_high",
                    models.GenericIPAddressField(
                        default=None,
                        blank=True,
                        help_text="Highest IP number of the range for IPs given to allocated nodes, must be in same network as dynamic range.",
                        null=True,
                        verbose_name="Static IP range high value",
                    ),
                ),
                (
                    "foreign_dhcp_ip",
                    models.GenericIPAddressField(
                        default=None, null=True, blank=True
                    ),
                ),
                (
                    "nodegroup",
                    models.ForeignKey(
                        to="maasserver.NodeGroup", on_delete=models.CASCADE
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Partition",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "uuid",
                    models.CharField(
                        max_length=36, unique=True, null=True, blank=True
                    ),
                ),
                (
                    "size",
                    models.BigIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(4194304)
                        ]
                    ),
                ),
                ("bootable", models.BooleanField(default=False)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="PartitionTable",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "table_type",
                    models.CharField(
                        default=None,
                        max_length=20,
                        choices=[
                            ("MBR", "Master boot record"),
                            ("GPT", "GUID parition table"),
                        ],
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Space",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        blank=True,
                        max_length=256,
                        null=True,
                        validators=[
                            maasserver.models.space.validate_space_name
                        ],
                    ),
                ),
            ],
            options={"verbose_name": "Space", "verbose_name_plural": "Spaces"},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="SSHKey",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "key",
                    models.TextField(
                        validators=[
                            maasserver.models.sshkey.validate_ssh_public_key
                        ]
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        editable=False,
                        to=settings.AUTH_USER_MODEL,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={"verbose_name": "SSH key"},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="SSLKey",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "key",
                    models.TextField(
                        validators=[maasserver.models.sslkey.validate_ssl_key]
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        editable=False,
                        to=settings.AUTH_USER_MODEL,
                        on_delete=models.CASCADE,
                    ),
                ),
            ],
            options={"verbose_name": "SSL key"},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="StaticIPAddress",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "ip",
                    models.GenericIPAddressField(
                        null=True,
                        default=None,
                        editable=False,
                        blank=True,
                        unique=True,
                        verbose_name="IP",
                    ),
                ),
                ("alloc_type", models.IntegerField(default=0, editable=False)),
                (
                    "hostname",
                    models.CharField(
                        default="",
                        max_length=255,
                        null=True,
                        blank=True,
                        validators=[maasserver.utils.dns.validate_hostname],
                    ),
                ),
            ],
            options={
                "verbose_name": "Static IP Address",
                "verbose_name_plural": "Static IP Addresses",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Subnet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        help_text="Identifying name for this subnet.",
                        max_length=255,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[.: \\w/-]+$"
                            )
                        ],
                    ),
                ),
                ("cidr", maasserver.fields.CIDRField(unique=True)),
                (
                    "gateway_ip",
                    models.GenericIPAddressField(null=True, blank=True),
                ),
                (
                    "dns_servers",
                    django.contrib.postgres.fields.ArrayField(
                        size=None,
                        base_field=models.TextField(),
                        null=True,
                        blank=True,
                        default=list,
                    ),
                ),
                (
                    "space",
                    models.ForeignKey(
                        to="maasserver.Space",
                        on_delete=django.db.models.deletion.PROTECT,
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Tag",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        max_length=256,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^[a-zA-Z0-9_-]+$"
                            )
                        ],
                    ),
                ),
                ("definition", models.TextField(blank=True)),
                ("comment", models.TextField(blank=True)),
                ("kernel_opts", models.TextField(null=True, blank=True)),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="UserProfile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE
                    ),
                ),
            ],
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="VLAN",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        blank=True,
                        max_length=256,
                        null=True,
                        validators=[
                            django.core.validators.RegexValidator("^[ \\w-]+$")
                        ],
                    ),
                ),
                ("vid", models.IntegerField()),
                ("mtu", models.IntegerField(default=1500)),
                (
                    "fabric",
                    models.ForeignKey(
                        to="maasserver.Fabric", on_delete=models.CASCADE
                    ),
                ),
            ],
            options={"verbose_name": "VLAN", "verbose_name_plural": "VLANs"},
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="Zone",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("created", models.DateTimeField(editable=False)),
                ("updated", models.DateTimeField(editable=False)),
                (
                    "name",
                    models.CharField(
                        unique=True,
                        max_length=256,
                        validators=[
                            django.core.validators.RegexValidator("^[\\w-]+$")
                        ],
                    ),
                ),
                ("description", models.TextField(blank=True)),
            ],
            options={
                "ordering": ["name"],
                "verbose_name": "Physical zone",
                "verbose_name_plural": "Physical zones",
            },
            bases=(maasserver.models.cleansave.CleanSave, models.Model),
        ),
        migrations.CreateModel(
            name="PhysicalBlockDevice",
            fields=[
                (
                    "blockdevice_ptr",
                    models.OneToOneField(
                        parent_link=True,
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        to="maasserver.BlockDevice",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "model",
                    models.CharField(
                        help_text="Model name of block device.",
                        max_length=255,
                        blank=True,
                    ),
                ),
                (
                    "serial",
                    models.CharField(
                        help_text="Serial number of block device.",
                        max_length=255,
                        blank=True,
                    ),
                ),
            ],
            bases=("maasserver.blockdevice",),
        ),
        migrations.CreateModel(
            name="VirtualBlockDevice",
            fields=[
                (
                    "blockdevice_ptr",
                    models.OneToOneField(
                        parent_link=True,
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        to="maasserver.BlockDevice",
                        on_delete=models.CASCADE,
                    ),
                ),
                (
                    "uuid",
                    models.CharField(
                        unique=True, max_length=36, editable=False
                    ),
                ),
            ],
            bases=("maasserver.blockdevice",),
        ),
        migrations.AddField(
            model_name="subnet",
            name="vlan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                default=0,
                to="maasserver.VLAN",
            ),
        ),
        migrations.AddField(
            model_name="staticipaddress",
            name="subnet",
            field=models.ForeignKey(
                blank=True,
                to="maasserver.Subnet",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="staticipaddress",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                default=None,
                blank=True,
                editable=False,
                to=settings.AUTH_USER_MODEL,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="partitiontable",
            name="block_device",
            field=models.ForeignKey(
                to="maasserver.BlockDevice", on_delete=models.CASCADE
            ),
        ),
        migrations.AddField(
            model_name="partition",
            name="partition_table",
            field=models.ForeignKey(
                related_name="partitions",
                to="maasserver.PartitionTable",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="nodegroupinterface",
            name="subnet",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                blank=True,
                to="maasserver.Subnet",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="nodegroupinterface",
            name="vlan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="maasserver.VLAN",
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="gateway_link_ipv4",
            field=models.ForeignKey(
                related_name="+",
                on_delete=django.db.models.deletion.SET_NULL,
                default=None,
                blank=True,
                editable=False,
                to="maasserver.StaticIPAddress",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="gateway_link_ipv6",
            field=models.ForeignKey(
                related_name="+",
                on_delete=django.db.models.deletion.SET_NULL,
                default=None,
                blank=True,
                editable=False,
                to="maasserver.StaticIPAddress",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="nodegroup",
            field=models.ForeignKey(
                to="maasserver.NodeGroup", null=True, on_delete=models.CASCADE
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                default=None,
                blank=True,
                editable=False,
                to=settings.AUTH_USER_MODEL,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="parent",
            field=models.ForeignKey(
                related_name="children",
                default=None,
                blank=True,
                to="maasserver.Node",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="tags",
            field=models.ManyToManyField(to="maasserver.Tag"),
        ),
        migrations.AddField(
            model_name="node",
            name="token",
            field=models.ForeignKey(
                editable=False,
                to="piston3.Token",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="node",
            name="zone",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.SET_DEFAULT,
                default=maasserver.models.node.get_default_zone,
                verbose_name="Physical zone",
                to="maasserver.Zone",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="licensekey",
            unique_together={("osystem", "distro_series")},
        ),
        migrations.AddField(
            model_name="interface",
            name="ip_addresses",
            field=models.ManyToManyField(
                to="maasserver.StaticIPAddress", blank=True
            ),
        ),
        migrations.AddField(
            model_name="interface",
            name="node",
            field=models.ForeignKey(
                blank=True,
                editable=False,
                to="maasserver.Node",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="interface",
            name="parents",
            field=models.ManyToManyField(
                to="maasserver.Interface",
                through="maasserver.InterfaceRelationship",
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="interface",
            name="vlan",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                default=0,
                to="maasserver.VLAN",
            ),
        ),
        migrations.AddField(
            model_name="filesystem",
            name="block_device",
            field=models.ForeignKey(
                blank=True,
                to="maasserver.BlockDevice",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="filesystem",
            name="cache_set",
            field=models.ForeignKey(
                related_name="filesystems",
                blank=True,
                to="maasserver.CacheSet",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="filesystem",
            name="filesystem_group",
            field=models.ForeignKey(
                related_name="filesystems",
                blank=True,
                to="maasserver.FilesystemGroup",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="filesystem",
            name="partition",
            field=models.ForeignKey(
                blank=True,
                to="maasserver.Partition",
                null=True,
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="node",
            field=models.ForeignKey(
                editable=False, to="maasserver.Node", on_delete=models.CASCADE
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="type",
            field=models.ForeignKey(
                editable=False,
                to="maasserver.EventType",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="downloadprogress",
            name="nodegroup",
            field=models.ForeignKey(
                editable=False,
                to="maasserver.NodeGroup",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="candidatename", unique_together={("name", "position")}
        ),
        migrations.AddField(
            model_name="bootresourcefile",
            name="largefile",
            field=models.ForeignKey(
                editable=False,
                to="maasserver.LargeFile",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AddField(
            model_name="bootresourcefile",
            name="resource_set",
            field=models.ForeignKey(
                related_name="files",
                editable=False,
                to="maasserver.BootResourceSet",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="bootresource",
            unique_together={("name", "architecture")},
        ),
        migrations.AddField(
            model_name="blockdevice",
            name="node",
            field=models.ForeignKey(
                editable=False, to="maasserver.Node", on_delete=models.CASCADE
            ),
        ),
        migrations.CreateModel(
            name="Bcache",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.filesystemgroup",),
        ),
        migrations.CreateModel(
            name="BondInterface",
            fields=[],
            options={
                "abstract": False,
                "verbose_name": "Bond",
                "proxy": True,
                "verbose_name_plural": "Bonds",
            },
            bases=("maasserver.interface",),
        ),
        migrations.CreateModel(
            name="Device",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.node",),
        ),
        migrations.CreateModel(
            name="PhysicalInterface",
            fields=[],
            options={
                "abstract": False,
                "verbose_name": "Physical interface",
                "proxy": True,
                "verbose_name_plural": "Physical interface",
            },
            bases=("maasserver.interface",),
        ),
        migrations.CreateModel(
            name="RAID",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.filesystemgroup",),
        ),
        migrations.CreateModel(
            name="UnknownInterface",
            fields=[],
            options={
                "abstract": False,
                "verbose_name": "Unknown interface",
                "proxy": True,
                "verbose_name_plural": "Unknown interfaces",
            },
            bases=("maasserver.interface",),
        ),
        migrations.CreateModel(
            name="VLANInterface",
            fields=[],
            options={
                "abstract": False,
                "verbose_name": "VLAN interface",
                "proxy": True,
                "verbose_name_plural": "VLAN interfaces",
            },
            bases=("maasserver.interface",),
        ),
        migrations.CreateModel(
            name="VolumeGroup",
            fields=[],
            options={"proxy": True},
            bases=("maasserver.filesystemgroup",),
        ),
        migrations.AlterUniqueTogether(
            name="vlan", unique_together={("vid", "fabric")}
        ),
        migrations.AddField(
            model_name="virtualblockdevice",
            name="filesystem_group",
            field=models.ForeignKey(
                related_name="virtual_devices",
                to="maasserver.FilesystemGroup",
                on_delete=models.CASCADE,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="subnet", unique_together={("name", "space")}
        ),
        migrations.AlterUniqueTogether(
            name="sslkey", unique_together={("user", "key")}
        ),
        migrations.AlterUniqueTogether(
            name="sshkey", unique_together={("user", "key")}
        ),
        migrations.AlterUniqueTogether(
            name="nodegroupinterface",
            unique_together={("nodegroup", "name")},
        ),
        migrations.AddField(
            model_name="node",
            name="boot_disk",
            field=models.ForeignKey(
                related_name="+",
                on_delete=django.db.models.deletion.SET_NULL,
                default=None,
                blank=True,
                editable=False,
                to="maasserver.PhysicalBlockDevice",
                null=True,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="filesystem",
            unique_together={
                ("partition", "acquired"),
                ("block_device", "acquired"),
            },
        ),
        migrations.AlterUniqueTogether(
            name="filestorage", unique_together={("filename", "owner")}
        ),
        migrations.AlterIndexTogether(
            name="event", index_together={("node", "id")}
        ),
        migrations.AlterUniqueTogether(
            name="bootsourceselection",
            unique_together={("boot_source", "os", "release")},
        ),
        migrations.AlterUniqueTogether(
            name="bootresourceset",
            unique_together={("resource", "version")},
        ),
        migrations.AlterUniqueTogether(
            name="bootresourcefile",
            unique_together={("resource_set", "filetype")},
        ),
        migrations.AlterUniqueTogether(
            name="blockdevice", unique_together={("node", "name")}
        ),
    ]

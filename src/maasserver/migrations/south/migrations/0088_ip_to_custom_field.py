from django.db import models
from south.db import db
# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.v2 import SchemaMigration


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'NodeGroupInterface.ip_range_high'
        db.alter_column('maasserver_nodegroupinterface', 'ip_range_high', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.static_ip_range_low'
        db.alter_column('maasserver_nodegroupinterface', 'static_ip_range_low', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.ip'
        db.alter_column('maasserver_nodegroupinterface', 'ip', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39))

        # Changing field 'NodeGroupInterface.ip_range_low'
        db.alter_column('maasserver_nodegroupinterface', 'ip_range_low', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.subnet_mask'
        db.alter_column('maasserver_nodegroupinterface', 'subnet_mask', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.broadcast_ip'
        db.alter_column('maasserver_nodegroupinterface', 'broadcast_ip', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.router_ip'
        db.alter_column('maasserver_nodegroupinterface', 'router_ip', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.foreign_dhcp_ip'
        db.alter_column('maasserver_nodegroupinterface', 'foreign_dhcp_ip', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.static_ip_range_high'
        db.alter_column('maasserver_nodegroupinterface', 'static_ip_range_high', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39, null=True))

        # Changing field 'StaticIPAddress.ip'
        db.alter_column('maasserver_staticipaddress', 'ip', self.gf('maasserver.fields.MAASIPAddressField')(unique=True, max_length=39))

        # Changing field 'DHCPLease.ip'
        db.alter_column('maasserver_dhcplease', 'ip', self.gf('maasserver.fields.MAASIPAddressField')(unique=True, max_length=39))

        # Changing field 'Network.ip'
        db.alter_column('maasserver_network', 'ip', self.gf('maasserver.fields.MAASIPAddressField')(unique=True, max_length=39))

        # Changing field 'Network.netmask'
        db.alter_column('maasserver_network', 'netmask', self.gf('maasserver.fields.MAASIPAddressField')(max_length=39))

    def backwards(self, orm):

        # Changing field 'NodeGroupInterface.ip_range_high'
        db.alter_column('maasserver_nodegroupinterface', 'ip_range_high', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.static_ip_range_low'
        db.alter_column('maasserver_nodegroupinterface', 'static_ip_range_low', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.ip'
        db.alter_column('maasserver_nodegroupinterface', 'ip', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39))

        # Changing field 'NodeGroupInterface.ip_range_low'
        db.alter_column('maasserver_nodegroupinterface', 'ip_range_low', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.subnet_mask'
        db.alter_column('maasserver_nodegroupinterface', 'subnet_mask', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.broadcast_ip'
        db.alter_column('maasserver_nodegroupinterface', 'broadcast_ip', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.router_ip'
        db.alter_column('maasserver_nodegroupinterface', 'router_ip', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.foreign_dhcp_ip'
        db.alter_column('maasserver_nodegroupinterface', 'foreign_dhcp_ip', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'NodeGroupInterface.static_ip_range_high'
        db.alter_column('maasserver_nodegroupinterface', 'static_ip_range_high', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, null=True))

        # Changing field 'StaticIPAddress.ip'
        db.alter_column('maasserver_staticipaddress', 'ip', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, unique=True))

        # Changing field 'DHCPLease.ip'
        db.alter_column('maasserver_dhcplease', 'ip', self.gf('django.db.models.fields.IPAddressField')(max_length=15, unique=True))

        # Changing field 'Network.ip'
        db.alter_column('maasserver_network', 'ip', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39, unique=True))

        # Changing field 'Network.netmask'
        db.alter_column('maasserver_network', 'netmask', self.gf('django.db.models.fields.GenericIPAddressField')(max_length=39))

    models = {
        'auth.group': {
            'Meta': {'object_name': 'Group'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['contenttypes.ContentType']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': "orm['auth.Group']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'symmetrical': 'False', 'related_name': "u'user_set'", 'blank': 'True', 'to': "orm['auth.Permission']"}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'maasserver.bootimage': {
            'Meta': {'unique_together': "((u'nodegroup', u'osystem', u'architecture', u'subarchitecture', u'release', u'purpose', u'label'),)", 'object_name': 'BootImage'},
            'architecture': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'default': "u'release'", 'max_length': '255'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"}),
            'osystem': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'purpose': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'release': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'subarchitecture': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'supported_subarches': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'xinstall_path': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'xinstall_type': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '30', 'null': 'True', 'blank': 'True'})
        },
        'maasserver.bootsource': {
            'Meta': {'object_name': 'BootSource'},
            'cluster': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'keyring_data': ('maasserver.fields.EditableBinaryField', [], {'blank': 'True'}),
            'keyring_filename': ('django.db.models.fields.FilePathField', [], {'max_length': '100', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        'maasserver.bootsourceselection': {
            'Meta': {'object_name': 'BootSourceSelection'},
            'arches': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'text'", 'null': 'True', 'blank': 'True'}),
            'boot_source': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.BootSource']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'labels': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'text'", 'null': 'True', 'blank': 'True'}),
            'release': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'subarches': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'text'", 'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.componenterror': {
            'Meta': {'object_name': 'ComponentError'},
            'component': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'error': ('django.db.models.fields.CharField', [], {'max_length': '1000'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.config': {
            'Meta': {'object_name': 'Config'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'value': ('maasserver.fields.JSONObjectField', [], {'null': 'True'})
        },
        'maasserver.dhcplease': {
            'Meta': {'object_name': 'DHCPLease'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'unique': 'True', 'max_length': '39'}),
            'mac': ('maasserver.fields.MACAddressField', [], {}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"})
        },
        'maasserver.downloadprogress': {
            'Meta': {'object_name': 'DownloadProgress'},
            'bytes_downloaded': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'error': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"}),
            'size': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.filestorage': {
            'Meta': {'unique_together': "((u'filename', u'owner'),)", 'object_name': 'FileStorage'},
            'content': ('metadataserver.fields.BinaryField', [], {'blank': 'True'}),
            'filename': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'default': "u'1ed17c44-0672-11e4-aedf-9c4e363b1c94'", 'unique': 'True', 'max_length': '36'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'maasserver.licensekey': {
            'Meta': {'unique_together': "((u'osystem', u'distro_series'),)", 'object_name': 'LicenseKey'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'distro_series': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'license_key': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'osystem': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.macaddress': {
            'Meta': {'object_name': 'MACAddress'},
            'cluster_interface': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['maasserver.NodeGroupInterface']", 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_addresses': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['maasserver.StaticIPAddress']", 'symmetrical': 'False', 'through': "orm['maasserver.MACStaticIPAddressLink']", 'blank': 'True'}),
            'mac_address': ('maasserver.fields.MACAddressField', [], {'unique': 'True'}),
            'networks': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['maasserver.Network']", 'symmetrical': 'False', 'blank': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Node']"}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.macstaticipaddresslink': {
            'Meta': {'unique_together': "((u'ip_address', u'mac_address'),)", 'object_name': 'MACStaticIPAddressLink'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip_address': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.StaticIPAddress']", 'unique': 'True'}),
            'mac_address': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.MACAddress']"}),
            'nic_alias': ('django.db.models.fields.IntegerField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.network': {
            'Meta': {'object_name': 'Network'},
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'unique': 'True', 'max_length': '39'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'netmask': ('maasserver.fields.MAASIPAddressField', [], {'max_length': '39'}),
            'vlan_tag': ('django.db.models.fields.PositiveSmallIntegerField', [], {'unique': 'True', 'null': 'True', 'blank': 'True'})
        },
        'maasserver.node': {
            'Meta': {'object_name': 'Node'},
            'agent_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'architecture': ('django.db.models.fields.CharField', [], {'max_length': '31'}),
            'cpu_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'distro_series': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'error': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'default': "u''", 'unique': 'True', 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'license_key': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            'memory': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'netboot': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']", 'null': 'True'}),
            'osystem': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'power_parameters': ('maasserver.fields.JSONObjectField', [], {'default': "u''", 'blank': 'True'}),
            'power_type': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '10', 'blank': 'True'}),
            'routers': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'macaddr'", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '10'}),
            'storage': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'system_id': ('django.db.models.fields.CharField', [], {'default': "u'node-1ececdb4-0672-11e4-aedf-9c4e363b1c94'", 'unique': 'True', 'max_length': '41'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['maasserver.Tag']", 'symmetrical': 'False'}),
            'token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'zone': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Zone']", 'on_delete': 'models.SET_DEFAULT'})
        },
        'maasserver.nodegroup': {
            'Meta': {'object_name': 'NodeGroup'},
            'api_key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '18'}),
            'api_token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'unique': 'True'}),
            'cluster_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'dhcp_key': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'maas_url': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '36'})
        },
        'maasserver.nodegroupinterface': {
            'Meta': {'unique_together': "((u'nodegroup', u'interface'),)", 'object_name': 'NodeGroupInterface'},
            'broadcast_ip': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'foreign_dhcp_ip': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'interface': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'max_length': '39'}),
            'ip_range_high': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'ip_range_low': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'management': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']"}),
            'router_ip': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'static_ip_range_high': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'static_ip_range_low': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'subnet_mask': ('maasserver.fields.MAASIPAddressField', [], {'default': 'None', 'max_length': '39', 'null': 'True', 'blank': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.sshkey': {
            'Meta': {'unique_together': "((u'user', u'key'),)", 'object_name': 'SSHKey'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.TextField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'maasserver.sslkey': {
            'Meta': {'unique_together': "((u'user', u'key'),)", 'object_name': 'SSLKey'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.TextField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['auth.User']"})
        },
        'maasserver.staticipaddress': {
            'Meta': {'object_name': 'StaticIPAddress'},
            'alloc_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('maasserver.fields.MAASIPAddressField', [], {'unique': 'True', 'max_length': '39'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'})
        },
        'maasserver.tag': {
            'Meta': {'object_name': 'Tag'},
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'definition': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kernel_opts': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'maasserver.userprofile': {
            'Meta': {'object_name': 'UserProfile'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'user': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['auth.User']", 'unique': 'True'})
        },
        'maasserver.zone': {
            'Meta': {'ordering': "[u'name']", 'object_name': 'Zone'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'piston.consumer': {
            'Meta': {'object_name': 'Consumer'},
            'description': ('django.db.models.fields.TextField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'pending'", 'max_length': '16'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'consumers'", 'null': 'True', 'to': "orm['auth.User']"})
        },
        'piston.token': {
            'Meta': {'object_name': 'Token'},
            'callback': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'callback_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'consumer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Consumer']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_approved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'timestamp': ('django.db.models.fields.IntegerField', [], {'default': '1404804793L'}),
            'token_type': ('django.db.models.fields.IntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tokens'", 'null': 'True', 'to': "orm['auth.User']"}),
            'verifier': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        }
    }

    complete_apps = ['maasserver']
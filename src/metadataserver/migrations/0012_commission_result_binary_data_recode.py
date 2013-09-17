# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

class Migration(DataMigration):

    def forwards(self, orm):
        "Write your forwards methods here."
        from metadataserver.fields import Bin
        for result in orm.NodeCommissionResult.objects.all():
            result.data_bin = Bin(result.data.encode("utf-8"))
            result.save()

    def backwards(self, orm):
        "Write your backwards methods here."
        for result in orm.NodeCommissionResult.objects.all():
            result.data = result.data_bin.decode("utf-8")
            result.save()

    models = {
        u'auth.group': {
            'Meta': {'object_name': 'Group'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '80'}),
            'permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'})
        },
        u'auth.permission': {
            'Meta': {'ordering': "(u'content_type__app_label', u'content_type__model', u'codename')", 'unique_together': "((u'content_type', u'codename'),)", 'object_name': 'Permission'},
            'codename': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '50'})
        },
        u'auth.user': {
            'Meta': {'object_name': 'User'},
            'date_joined': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'email': ('django.db.models.fields.EmailField', [], {'unique': 'True', 'max_length': '75', 'blank': 'True'}),
            'first_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Group']", 'symmetrical': 'False', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_staff': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'is_superuser': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'last_name': ('django.db.models.fields.CharField', [], {'max_length': '30', 'blank': 'True'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'user_permissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['auth.Permission']", 'symmetrical': 'False', 'blank': 'True'}),
            'username': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '30'})
        },
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'maasserver.node': {
            'Meta': {'object_name': 'Node'},
            'after_commissioning_action': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'architecture': ('django.db.models.fields.CharField', [], {'default': "u'i386/generic'", 'max_length': '31'}),
            'cpu_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'distro_series': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'null': 'True', 'blank': 'True'}),
            'error': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'hardware_details': ('maasserver.fields.XMLField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'default': "u''", 'unique': 'True', 'max_length': '255', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'memory': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'netboot': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.NodeGroup']", 'null': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': u"orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'power_parameters': ('maasserver.fields.JSONObjectField', [], {'default': "u''", 'blank': 'True'}),
            'power_type': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '10', 'blank': 'True'}),
            'routers': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'macaddr'", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '10'}),
            'storage': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'system_id': ('django.db.models.fields.CharField', [], {'default': "u'node-e664d6e6-1cc3-11e3-92b1-000c29baa6bf'", 'unique': 'True', 'max_length': '41'}),
            'tags': ('django.db.models.fields.related.ManyToManyField', [], {'to': u"orm['maasserver.Tag']", 'symmetrical': 'False'}),
            'token': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['piston.Token']", 'null': 'True'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'maasserver.nodegroup': {
            'Meta': {'object_name': 'NodeGroup'},
            'api_key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '18'}),
            'api_token': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['piston.Token']", 'unique': 'True'}),
            'cluster_name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '100', 'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'dhcp_key': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'maas_url': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {}),
            'uuid': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '36'})
        },
        u'maasserver.tag': {
            'Meta': {'object_name': 'Tag'},
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'definition': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'kernel_opts': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'metadataserver.commissioningscript': {
            'Meta': {'object_name': 'CommissioningScript'},
            'content': ('metadataserver.fields.BinaryField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        u'metadataserver.nodecommissionresult': {
            'Meta': {'unique_together': "((u'node', u'name'),)", 'object_name': 'NodeCommissionResult'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'data': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '1048576', 'blank': 'True'}),
            'data_bin': ('metadataserver.fields.BinaryField', [], {'default': "''", 'max_length': '1048576', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.Node']"}),
            'script_result': ('django.db.models.fields.IntegerField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        u'metadataserver.nodekey': {
            'Meta': {'object_name': 'NodeKey'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '18'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.Node']", 'unique': 'True'}),
            'token': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['piston.Token']", 'unique': 'True'})
        },
        u'metadataserver.nodeuserdata': {
            'Meta': {'object_name': 'NodeUserData'},
            'data': ('metadataserver.fields.BinaryField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['maasserver.Node']", 'unique': 'True'})
        },
        u'piston.consumer': {
            'Meta': {'object_name': 'Consumer'},
            'description': ('django.db.models.fields.TextField', [], {}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'pending'", 'max_length': '16'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'consumers'", 'null': 'True', 'to': u"orm['auth.User']"})
        },
        u'piston.token': {
            'Meta': {'object_name': 'Token'},
            'callback': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'callback_confirmed': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'consumer': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['piston.Consumer']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_approved': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'key': ('django.db.models.fields.CharField', [], {'max_length': '18'}),
            'secret': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'timestamp': ('django.db.models.fields.IntegerField', [], {'default': '1379111345L'}),
            'token_type': ('django.db.models.fields.IntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tokens'", 'null': 'True', 'to': u"orm['auth.User']"}),
            'verifier': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        }
    }

    complete_apps = ['metadataserver']
    symmetrical = True

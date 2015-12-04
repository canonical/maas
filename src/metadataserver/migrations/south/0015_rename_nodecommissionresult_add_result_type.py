from django.db import models
from metadataserver.enum import RESULT_TYPE
from south.db import db
# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.v2 import SchemaMigration


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'NodeCommissionResult.status'
        db.add_column('metadataserver_nodecommissionresult', 'result_type',
                      self.gf('django.db.models.fields.IntegerField')(default=RESULT_TYPE.COMMISSIONING),
                      keep_default=False)
        db.rename_table('metadataserver_nodecommissionresult', 'metadataserver_noderesult')

    def backwards(self, orm):
        db.rename_table('metadataserver_noderesult', 'metadataserver_nodecommissionresult')
        # Deleting field 'NodeCommissionResult.status'
        db.delete_column('metadataserver_nodecommissionresult', 'result_type')


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
        'maasserver.node': {
            'Meta': {'object_name': 'Node'},
            'agent_name': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'architecture': ('django.db.models.fields.CharField', [], {'max_length': '31'}),
            'boot_type': ('django.db.models.fields.CharField', [], {'default': "u'fastpath'", 'max_length': '20'}),
            'cpu_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'distro_series': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'error': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '255', 'blank': 'True'}),
            'error_description': ('django.db.models.fields.TextField', [], {'default': "u''", 'blank': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'default': "u''", 'unique': 'True', 'max_length': '255', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'license_key': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True', 'blank': 'True'}),
            'memory': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'netboot': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'nodegroup': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.NodeGroup']", 'null': 'True'}),
            'osystem': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '20', 'blank': 'True'}),
            'owner': ('django.db.models.fields.related.ForeignKey', [], {'default': 'None', 'to': "orm['auth.User']", 'null': 'True', 'blank': 'True'}),
            'power_parameters': ('maasserver.fields.JSONObjectField', [], {'default': "u''", 'blank': 'True'}),
            'power_state': ('django.db.models.fields.CharField', [], {'default': "u'unknown'", 'max_length': '10'}),
            'power_type': ('django.db.models.fields.CharField', [], {'default': "u''", 'max_length': '10', 'blank': 'True'}),
            'routers': ('djorm_pgarray.fields.ArrayField', [], {'default': 'None', 'dbtype': "u'macaddr'", 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.IntegerField', [], {'default': '0', 'max_length': '10'}),
            'storage': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'system_id': ('django.db.models.fields.CharField', [], {'default': "u'node-8fa4490a-20c2-11e4-97b9-e82aea220bd2'", 'unique': 'True', 'max_length': '41'}),
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
        'maasserver.zone': {
            'Meta': {'ordering': "[u'name']", 'object_name': 'Zone'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'description': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '256'}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'metadataserver.commissioningscript': {
            'Meta': {'object_name': 'CommissioningScript'},
            'content': ('metadataserver.fields.BinaryField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'metadataserver.nodekey': {
            'Meta': {'object_name': 'NodeKey'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'key': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '18'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Node']", 'unique': 'True'}),
            'token': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['piston.Token']", 'unique': 'True'})
        },
        'metadataserver.noderesult': {
            'Meta': {'unique_together': "((u'node', u'name'),)", 'object_name': 'NodeResult'},
            'created': ('django.db.models.fields.DateTimeField', [], {}),
            'data': ('metadataserver.fields.BinaryField', [], {'default': "''", 'max_length': '1048576', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Node']"}),
            'result_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'script_result': ('django.db.models.fields.IntegerField', [], {}),
            'updated': ('django.db.models.fields.DateTimeField', [], {})
        },
        'metadataserver.nodeuserdata': {
            'Meta': {'object_name': 'NodeUserData'},
            'data': ('metadataserver.fields.BinaryField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['maasserver.Node']", 'unique': 'True'})
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
            'timestamp': ('django.db.models.fields.IntegerField', [], {'default': '1407698073L'}),
            'token_type': ('django.db.models.fields.IntegerField', [], {}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'tokens'", 'null': 'True', 'to': "orm['auth.User']"}),
            'verifier': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        }
    }

    complete_apps = ['metadataserver']
